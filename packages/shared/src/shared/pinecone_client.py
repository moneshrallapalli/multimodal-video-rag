"""Small Pinecone HTTP client shared by worker and query graph."""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import settings
from .schemas import RetrievalHit, VectorRecord

logger = logging.getLogger(__name__)

# Single retry on transient (5xx / connection) failures defends against a brief
# Pinecone hiccup turning every search into a silent no-answer. Two attempts is
# enough — anything systematic should fail loudly so the operator sees it.
_MAX_RETRIES = 2
_BASE_BACKOFF_SECONDS = 0.25


@dataclass(frozen=True)
class PineconeIndexInfo:
    name: str
    host: str
    dimension: int
    metric: str


class PineconeIndexClient:
    def __init__(self, *, api_key: str, info: PineconeIndexInfo) -> None:
        self.api_key = api_key
        self.info = info

    @classmethod
    def from_index_name(
        cls,
        index_name: str,
        *,
        api_key: str | None = None,
        expected_dim: int | None = None,
        expected_metric: str | None = None,
    ) -> PineconeIndexClient:
        key = api_key or settings.pinecone_api_key
        if not key:
            raise RuntimeError("PINECONE_API_KEY is required")
        info = _lookup_index(index_name, api_key=key)
        dim = expected_dim or settings.embed_dim
        if info.dimension != dim:
            raise ValueError(f"Pinecone index {index_name} dimension {info.dimension} != {dim}")
        # The transcript index is dotproduct and the visual index is cosine; their
        # score distributions differ. Catching a rebuild that swaps the metric
        # here is cheaper than tracking down weird ranking drift in production.
        if expected_metric and info.metric != expected_metric:
            raise ValueError(
                f"Pinecone index {index_name} metric {info.metric!r} != "
                f"expected {expected_metric!r}"
            )
        return cls(api_key=key, info=info)

    def upsert(self, records: list[VectorRecord], *, namespace: str | None = None) -> int:
        if not records:
            return 0
        payload: dict[str, Any] = {
            "vectors": [_record_payload(record) for record in records],
        }
        if namespace:
            payload["namespace"] = namespace
        self._request("/vectors/upsert", payload)
        return len(records)

    def query(
        self,
        vector: list[float],
        *,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
        namespace: str | None = None,
        sparse_vector: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        payload: dict[str, Any] = {
            "vector": vector,
            "topK": top_k,
            "includeMetadata": True,
        }
        if metadata_filter:
            payload["filter"] = metadata_filter
        if namespace:
            payload["namespace"] = namespace
        # Pinecone serverless hybrid: send `sparseVector` alongside the dense
        # vector. Caller is responsible for alpha-scaling (see hybrid_blend()).
        if sparse_vector and sparse_vector.get("indices"):
            payload["sparseVector"] = {
                "indices": list(sparse_vector["indices"]),
                "values": list(sparse_vector["values"]),
            }
        data = self._request("/query", payload)
        return [
            RetrievalHit(
                id=str(match["id"]),
                score=float(match.get("score", 0.0)),
                metadata=match.get("metadata") or {},
            )
            for match in data.get("matches", [])
        ]

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        url = f"https://{self.info.host}{path}"
        last_exc: BaseException | None = None
        for attempt in range(_MAX_RETRIES + 1):
            req = Request(
                url,
                data=body,
                headers={"Api-Key": self.api_key, "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urlopen(req, timeout=30) as response:
                    raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
            except HTTPError as exc:
                last_exc = exc
                if exc.code < 500 or attempt == _MAX_RETRIES:
                    # 4xx errors are caller bugs (bad payload, wrong index) —
                    # never worth retrying. Final retry exhaustion also re-raises.
                    detail = exc.read().decode("utf-8")[:500]
                    raise RuntimeError(f"Pinecone {self.info.name}{path} failed: {detail}") from exc
                logger.warning(
                    "pinecone_retry index=%s path=%s status=%s attempt=%s",
                    self.info.name,
                    path,
                    exc.code,
                    attempt + 1,
                )
            except URLError as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    raise RuntimeError(
                        f"Pinecone {self.info.name}{path} unreachable: {exc.reason}"
                    ) from exc
                logger.warning(
                    "pinecone_retry index=%s path=%s reason=%s attempt=%s",
                    self.info.name,
                    path,
                    exc.reason,
                    attempt + 1,
                )
            # Exponential backoff with jitter: 0-0.5s, then 0.25-1s.
            sleep_for = _BASE_BACKOFF_SECONDS * (2**attempt) * (0.5 + random.random())
            time.sleep(sleep_for)
        # Defensive — unreachable in practice because the loop above either returns or raises.
        raise RuntimeError(f"Pinecone {self.info.name}{path} exhausted retries") from last_exc


def _record_payload(record: VectorRecord) -> dict[str, Any]:
    """Render a VectorRecord for Pinecone, omitting sparse_values when empty.

    Pinecone rejects payloads with empty sparse_values, so we strip them rather
    than send `{"indices": [], "values": []}`.
    """
    payload = record.model_dump(exclude_none=True)
    sparse = payload.get("sparse_values")
    if sparse and not sparse.get("indices"):
        payload.pop("sparse_values", None)
    return payload


def hybrid_blend(
    dense: list[float],
    sparse: dict[str, Any],
    *,
    alpha: float,
) -> tuple[list[float], dict[str, Any]]:
    """Pinecone's standard alpha-blending convention.

    alpha=1.0 → pure dense; alpha=0.0 → pure sparse. The serverless query API
    blends by scaling both sides on the client. Returns (dense, sparse) ready
    to pass to `query(vector=, sparse_vector=)`.
    """
    alpha = max(0.0, min(1.0, alpha))
    scaled_dense = [value * alpha for value in dense]
    sparse_values = sparse.get("values") or []
    scaled_sparse = {
        "indices": list(sparse.get("indices") or []),
        "values": [value * (1.0 - alpha) for value in sparse_values],
    }
    return scaled_dense, scaled_sparse


def _lookup_index(index_name: str, *, api_key: str) -> PineconeIndexInfo:
    req = Request("https://api.pinecone.io/indexes", headers={"Api-Key": api_key})
    try:
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")[:500]
        raise RuntimeError(f"Pinecone index lookup failed: {detail}") from exc

    for index in data.get("indexes", []):
        if index.get("name") == index_name:
            host = index.get("host")
            if not host:
                raise RuntimeError(f"Pinecone index {index_name} did not include a host")
            return PineconeIndexInfo(
                name=index_name,
                host=host,
                dimension=int(index["dimension"]),
                metric=str(index["metric"]),
            )
    raise RuntimeError(f"Pinecone index {index_name} was not found")
