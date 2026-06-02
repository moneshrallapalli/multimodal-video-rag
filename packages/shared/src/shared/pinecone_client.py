"""Small Pinecone HTTP client shared by worker and query graph."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .config import settings
from .schemas import RetrievalHit, VectorRecord


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
    ) -> PineconeIndexClient:
        key = api_key or settings.pinecone_api_key
        if not key:
            raise RuntimeError("PINECONE_API_KEY is required")
        info = _lookup_index(index_name, api_key=key)
        dim = expected_dim or settings.embed_dim
        if info.dimension != dim:
            raise ValueError(f"Pinecone index {index_name} dimension {info.dimension} != {dim}")
        return cls(api_key=key, info=info)

    def upsert(self, records: list[VectorRecord], *, namespace: str | None = None) -> int:
        if not records:
            return 0
        payload: dict[str, Any] = {
            "vectors": [record.model_dump() for record in records],
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
        req = Request(
            f"https://{self.info.host}{path}",
            data=body,
            headers={
                "Api-Key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8")[:500]
            raise RuntimeError(f"Pinecone {self.info.name}{path} failed: {detail}") from exc
        return json.loads(raw) if raw else {}


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
