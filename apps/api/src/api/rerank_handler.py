"""Dedicated Lambda handler for warmed cross-encoder reranking."""

from __future__ import annotations

import logging
from typing import Any

from sentence_transformers import CrossEncoder

logger = logging.getLogger("video_rag.reranker")
logger.setLevel(logging.INFO)

_MODEL_ID = "BAAI/bge-reranker-base"
_MODEL = CrossEncoder(_MODEL_ID)


def handler(event: dict[str, Any], context: Any) -> dict[str, list[float]]:
    pairs = event.get("pairs", [])
    if not isinstance(pairs, list):
        raise ValueError("Expected pairs to be a list")
    sentences: list[tuple[str, str]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("Each pair must be an object")
        query = str(pair.get("query") or "")
        text = str(pair.get("text") or "")
        if not query or not text:
            raise ValueError("Each pair needs query and text")
        sentences.append((query, text))
    if len(sentences) > 20:
        raise ValueError("Reranker accepts at most 20 pairs per request")

    scores = [float(score) for score in _MODEL.predict(sentences)]
    logger.info("reranker_request pairs=%s", len(sentences))
    return {"scores": scores}
