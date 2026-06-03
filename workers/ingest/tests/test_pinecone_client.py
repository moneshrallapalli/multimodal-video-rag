"""Pinecone HTTP helper tests."""

from __future__ import annotations

import io
import json
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from shared.pinecone_client import PineconeIndexClient, PineconeIndexInfo
from shared.schemas import VectorRecord


class FakeResponse:
    def __init__(self, body: dict):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self.body


def test_upsert_posts_vector_records(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req, timeout))
        return FakeResponse({"upsertedCount": 1})

    monkeypatch.setattr("shared.pinecone_client.urlopen", fake_urlopen)
    client = PineconeIndexClient(
        api_key="test-key",
        info=PineconeIndexInfo(
            name="transcript", host="example.pinecone.io", dimension=3, metric="dotproduct"
        ),
    )

    count = client.upsert(
        [
            VectorRecord(
                id="vid:transcript:000001",
                values=[0.1, 0.2, 0.3],
                metadata={"video_id": "vid", "modality": "transcript"},
            )
        ]
    )

    assert count == 1
    req, timeout = calls[0]
    assert timeout == 30
    assert req.full_url == "https://example.pinecone.io/vectors/upsert"
    body = json.loads(req.data.decode("utf-8"))
    assert body["vectors"][0]["id"] == "vid:transcript:000001"
    assert body["vectors"][0]["metadata"]["modality"] == "transcript"


def test_query_returns_retrieval_hits(monkeypatch):
    def fake_urlopen(req, timeout):
        return FakeResponse(
            {
                "matches": [
                    {
                        "id": "vid:frame:000001",
                        "score": 0.88,
                        "metadata": {"video_id": "vid", "timestamp_seconds": 12},
                    }
                ]
            }
        )

    monkeypatch.setattr("shared.pinecone_client.urlopen", fake_urlopen)
    client = PineconeIndexClient(
        api_key="test-key",
        info=PineconeIndexInfo(
            name="visual", host="example.pinecone.io", dimension=3, metric="cosine"
        ),
    )

    hits = client.query([0.1, 0.2, 0.3])

    assert len(hits) == 1
    assert hits[0].id == "vid:frame:000001"
    assert hits[0].score == 0.88
    assert hits[0].metadata["timestamp_seconds"] == 12


def _client() -> PineconeIndexClient:
    return PineconeIndexClient(
        api_key="test-key",
        info=PineconeIndexInfo(
            name="transcript", host="example.pinecone.io", dimension=3, metric="dotproduct"
        ),
    )


def _http_error(status: int = 503) -> HTTPError:
    return HTTPError(
        url="https://example.pinecone.io/query",
        code=status,
        msg=f"HTTP {status}",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"transient"}'),
    )


def test_request_retries_transient_5xx_then_succeeds(monkeypatch):
    """A single transient 5xx must not silently turn into a no-answer; the client
    retries once and surfaces the eventual success."""
    monkeypatch.setattr("shared.pinecone_client.time.sleep", lambda _s: None)
    calls = []

    def flaky(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise _http_error(503)
        return FakeResponse({"matches": []})

    monkeypatch.setattr("shared.pinecone_client.urlopen", flaky)

    hits = _client().query([0.1, 0.2, 0.3])
    assert hits == []
    assert len(calls) == 2  # initial + 1 retry


def test_request_does_not_retry_client_errors(monkeypatch):
    """4xx errors are caller bugs (bad payload / wrong index) — never retry."""
    monkeypatch.setattr("shared.pinecone_client.time.sleep", lambda _s: None)
    calls = []

    def always_400(req, timeout):
        calls.append(req.full_url)
        raise _http_error(400)

    monkeypatch.setattr("shared.pinecone_client.urlopen", always_400)

    with pytest.raises(RuntimeError, match="transient"):
        _client().query([0.1, 0.2, 0.3])
    assert len(calls) == 1  # no retries


def test_request_retries_url_errors(monkeypatch):
    """Connection errors (DNS, refused) also get retried with backoff."""
    monkeypatch.setattr("shared.pinecone_client.time.sleep", lambda _s: None)
    calls = []

    def flaky(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise URLError("connection refused")
        return FakeResponse({"matches": []})

    monkeypatch.setattr("shared.pinecone_client.urlopen", flaky)
    assert _client().query([0.1, 0.2, 0.3]) == []
    assert len(calls) == 2


def test_upsert_includes_sparse_values_when_present(monkeypatch):
    """The Pinecone wire format expects `sparse_values` alongside `values` for
    hybrid records. Empty sparse vectors must be omitted (Pinecone rejects them)."""
    captured: dict[str, Any] = {}

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse({"upsertedCount": 2})

    monkeypatch.setattr("shared.pinecone_client.urlopen", fake_urlopen)
    client = _client()

    from shared.schemas import SparseVector

    client.upsert(
        [
            VectorRecord(
                id="v:1",
                values=[0.1, 0.2, 0.3],
                metadata={"video_id": "v"},
                sparse_values=SparseVector(indices=[42, 7], values=[1.5, 0.8]),
            ),
            VectorRecord(
                id="v:2",
                values=[0.4, 0.5, 0.6],
                metadata={"video_id": "v"},
                # No sparse vector — must be omitted from the wire payload.
                sparse_values=None,
            ),
        ]
    )

    vectors = captured["body"]["vectors"]
    assert vectors[0]["sparse_values"] == {"indices": [42, 7], "values": [1.5, 0.8]}
    assert "sparse_values" not in vectors[1]


def test_query_sends_sparse_vector_when_provided(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse({"matches": []})

    monkeypatch.setattr("shared.pinecone_client.urlopen", fake_urlopen)
    _client().query(
        [0.1, 0.2, 0.3],
        sparse_vector={"indices": [10, 20], "values": [0.9, 0.5]},
    )
    assert captured["body"]["sparseVector"] == {
        "indices": [10, 20],
        "values": [0.9, 0.5],
    }


def test_query_omits_sparse_vector_when_empty(monkeypatch):
    """An empty sparse vector at query time must not be sent — Pinecone errors on it."""
    captured: dict[str, Any] = {}

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse({"matches": []})

    monkeypatch.setattr("shared.pinecone_client.urlopen", fake_urlopen)
    _client().query([0.1, 0.2, 0.3], sparse_vector={"indices": [], "values": []})
    assert "sparseVector" not in captured["body"]


def test_hybrid_blend_alpha_extremes_and_midpoint():
    """alpha=1 = pure dense, alpha=0 = pure sparse, 0.7 blends both."""
    from shared.pinecone_client import hybrid_blend

    dense, sparse = hybrid_blend([1.0, 2.0], {"indices": [1], "values": [0.5]}, alpha=1.0)
    assert dense == [1.0, 2.0]
    assert sparse["values"] == [0.0]

    dense, sparse = hybrid_blend([1.0, 2.0], {"indices": [1], "values": [0.5]}, alpha=0.0)
    assert dense == [0.0, 0.0]
    assert sparse["values"] == [0.5]

    dense, sparse = hybrid_blend([2.0], {"indices": [1], "values": [1.0]}, alpha=0.7)
    assert dense == [pytest.approx(1.4)]
    assert sparse["values"] == [pytest.approx(0.3)]


def test_from_index_name_asserts_metric_matches_expectation(monkeypatch):
    """Catch a future operator who rebuilds an index with the wrong metric. A
    silent metric swap would drift retrieval quality without any error signal."""

    def fake_lookup(name, *, api_key):
        return PineconeIndexInfo(
            name=name, host="example.pinecone.io", dimension=3, metric="cosine"
        )

    monkeypatch.setattr("shared.pinecone_client._lookup_index", fake_lookup)

    # Expected dotproduct (transcript) but the index is cosine → raises.
    with pytest.raises(ValueError, match="metric"):
        PineconeIndexClient.from_index_name(
            "transcript",
            api_key="key",
            expected_dim=3,
            expected_metric="dotproduct",
        )

    # Matching metric → succeeds (no assertion error).
    client = PineconeIndexClient.from_index_name(
        "visual", api_key="key", expected_dim=3, expected_metric="cosine"
    )
    assert client.info.metric == "cosine"
