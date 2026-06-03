"""Remote reranker client tests."""

from __future__ import annotations

import json

import pytest
from api.reranking import LambdaCrossEncoderReranker


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


def test_lambda_cross_encoder_reranker_rejects_invalid_payload():
    client = FakeLambdaClient({"Payload": FakePayload({"scores": [0.3]})})
    reranker = LambdaCrossEncoderReranker(function_name="reranker-live", client=client)

    with pytest.raises(RuntimeError, match="invalid score payload"):
        reranker.predict([("query", "candidate one"), ("query", "candidate two")])
