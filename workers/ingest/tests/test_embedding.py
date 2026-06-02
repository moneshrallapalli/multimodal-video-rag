"""Bedrock embedding helper tests."""

from __future__ import annotations

import io
import json

import pytest
from ingest.embedding import BedrockEmbedder


class FakeBedrock:
    def __init__(self, vector):
        self.vector = vector
        self.calls = []

    def invoke_model(self, **kwargs):
        self.calls.append(kwargs)
        return {"body": io.BytesIO(json.dumps({"embedding": self.vector}).encode("utf-8"))}


def test_embed_text_invokes_titan_text_and_validates_dimension():
    client = FakeBedrock([0.1, 0.2, 0.3])
    embedder = BedrockEmbedder(
        client=client,
        text_model_id="text-model",
        image_model_id="image-model",
        expected_dim=3,
    )

    vector = embedder.embed_text("hello")

    assert vector == [0.1, 0.2, 0.3]
    assert client.calls[0]["modelId"] == "text-model"
    body = json.loads(client.calls[0]["body"])
    assert body["inputText"] == "hello"
    assert body["dimensions"] == 3
    assert body["normalize"] is True


def test_embed_image_encodes_file(tmp_path):
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"fake-jpeg")
    client = FakeBedrock([1, 2, 3])
    embedder = BedrockEmbedder(
        client=client,
        text_model_id="text-model",
        image_model_id="image-model",
        expected_dim=3,
    )

    vector = embedder.embed_image(image)

    assert vector == [1.0, 2.0, 3.0]
    assert client.calls[0]["modelId"] == "image-model"
    body = json.loads(client.calls[0]["body"])
    assert body["inputImage"]
    assert body["embeddingConfig"]["outputEmbeddingLength"] == 3


def test_embedding_dimension_mismatch_raises():
    embedder = BedrockEmbedder(
        client=FakeBedrock([0.1, 0.2]),
        text_model_id="text-model",
        image_model_id="image-model",
        expected_dim=3,
    )

    with pytest.raises(ValueError, match="dimension"):
        embedder.embed_text("hello")
