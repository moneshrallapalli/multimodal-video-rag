"""Reranker client tests — remote (Lambda) and local (in-process) paths."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from api.reranking import LambdaCrossEncoderReranker, LocalCrossEncoderReranker


class FakePayload:
    def __init__(self, body: dict) -> None:
        self.body = body

    def read(self) -> bytes:
        return json.dumps(self.body).encode("utf-8")


class FakeLambdaClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_lambda_cross_encoder_reranker_invokes_remote_function():
    client = FakeLambdaClient({"Payload": FakePayload({"scores": [0.3, 1.2]})})
    reranker = LambdaCrossEncoderReranker(function_name="reranker-live", client=client)

    scores = reranker.predict([("query", "candidate one"), ("query", "candidate two")])

    assert scores == [0.3, 1.2]
    assert client.calls[0]["FunctionName"] == "reranker-live"
    payload = json.loads(client.calls[0]["Payload"].decode("utf-8"))
    assert payload["pairs"][0] == {"query": "query", "text": "candidate one"}


def test_local_cross_encoder_reranker_uses_injected_model():
    """LocalCrossEncoderReranker accepts a pre-built model via dependency injection
    so tests never load the real weights."""

    class FakeModel:
        def predict(self, pairs: list) -> Sequence[float]:
            return [float(i) for i in range(len(pairs))]

    reranker = LocalCrossEncoderReranker.__new__(LocalCrossEncoderReranker)
    reranker._model = FakeModel()

    scores = reranker.predict([("q", "a"), ("q", "b"), ("q", "c")])

    assert list(scores) == [0.0, 1.0, 2.0]


def test_lambda_cross_encoder_reranker_rejects_invalid_payload():
    client = FakeLambdaClient({"Payload": FakePayload({"scores": [0.3]})})
    reranker = LambdaCrossEncoderReranker(function_name="reranker-live", client=client)

    with pytest.raises(RuntimeError, match="invalid score payload"):
        reranker.predict([("query", "candidate one"), ("query", "candidate two")])
