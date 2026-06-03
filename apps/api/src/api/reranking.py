"""Cross-encoder reranker clients for the public API."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import boto3


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
