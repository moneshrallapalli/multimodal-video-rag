"""Pinecone HTTP helper tests."""

from __future__ import annotations

import json

from ingest.pinecone_client import PineconeIndexClient, PineconeIndexInfo
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

    monkeypatch.setattr("ingest.pinecone_client.urlopen", fake_urlopen)
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

    monkeypatch.setattr("ingest.pinecone_client.urlopen", fake_urlopen)
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
