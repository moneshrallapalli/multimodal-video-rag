"""Bedrock embedding client shared by worker and query graph."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import boto3

from .config import settings


class BedrockEmbedder:
    def __init__(
        self,
        *,
        client: Any | None = None,
        region: str | None = None,
        text_model_id: str | None = None,
        image_model_id: str | None = None,
        expected_dim: int | None = None,
    ) -> None:
        self.client = client or boto3.client(
            "bedrock-runtime", region_name=region or settings.aws_region
        )
        self.text_model_id = text_model_id or settings.bedrock_text_embed_model_id
        self.image_model_id = image_model_id or settings.bedrock_image_embed_model_id
        self.expected_dim = expected_dim or settings.embed_dim

    def embed_text(self, text: str) -> list[float]:
        body = {
            "inputText": text,
            "dimensions": self.expected_dim,
            "normalize": True,
        }
        payload = self._invoke(self.text_model_id, body)
        vector = payload.get("embedding") or payload.get("embeddingsByType", {}).get("float")
        return self._validate_vector(vector, label="text")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]

    def embed_image(self, image_path: Path) -> list[float]:
        body = {
            "inputImage": base64.b64encode(image_path.read_bytes()).decode("ascii"),
            "embeddingConfig": {"outputEmbeddingLength": self.expected_dim},
        }
        payload = self._invoke(self.image_model_id, body)
        return self._validate_vector(payload.get("embedding"), label="image")

    def embed_visual_query(self, text: str) -> list[float]:
        body = {
            "inputText": text,
            "embeddingConfig": {"outputEmbeddingLength": self.expected_dim},
        }
        payload = self._invoke(self.image_model_id, body)
        return self._validate_vector(payload.get("embedding"), label="visual query")

    def _invoke(self, model_id: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self.client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        return json.loads(response["body"].read())

    def _validate_vector(self, vector: Any, *, label: str) -> list[float]:
        if not isinstance(vector, list):
            raise ValueError(f"Bedrock {label} embedding response did not include a vector")
        if len(vector) != self.expected_dim:
            raise ValueError(
                f"Bedrock {label} embedding dimension {len(vector)} != expected {self.expected_dim}"
            )
        return [float(value) for value in vector]
