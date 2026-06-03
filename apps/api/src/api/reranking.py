"""Cross-encoder reranker clients for the public API."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

import boto3

logger = logging.getLogger("video_rag.api.reranking")

_DEFAULT_MODEL_ID = "BAAI/bge-reranker-base"


class LocalCrossEncoderReranker:
    """Load the cross-encoder model that is baked into this Lambda image and
    run inference in-process. No network call; model loads once per container
    from /var/task/.cache/sentence-transformers."""

    def __init__(self, model_id: str = _DEFAULT_MODEL_ID) -> None:
        from sentence_transformers import CrossEncoder

        logger.info("cross_encoder_local_load model=%s", model_id)
        self._model = CrossEncoder(model_id)
        logger.info("cross_encoder_local_ready model=%s", model_id)

    def predict(self, sentences: Sequence[tuple[str, str]]) -> Sequence[float]:
        return [float(s) for s in self._model.predict(list(sentences))]


class LambdaCrossEncoderReranker:
    """Invoke the warmed reranker Lambda instead of loading the model in the API."""

    def __init__(self, *, function_name: str, client: Any | None = None) -> None:
        self.function_name = function_name
        self.client = client or boto3.client("lambda")

    def predict(self, sentences: Sequence[tuple[str, str]]) -> Sequence[float]:
        if not sentences:
            return []
        payload = {
            "pairs": [{"query": query, "text": text} for query, text in sentences],
        }
        response = self.client.invoke(
            FunctionName=self.function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode("utf-8"),
        )
        raw_body = response["Payload"].read().decode("utf-8")
        if response.get("FunctionError"):
            raise RuntimeError(f"reranker lambda failed: {raw_body[:500]}")
        data = json.loads(raw_body)
        scores = data.get("scores")
        if not isinstance(scores, list) or len(scores) != len(sentences):
            raise RuntimeError("reranker lambda returned an invalid score payload")
        return [float(score) for score in scores]
