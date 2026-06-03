"""Frame captioning via Bedrock Claude Haiku."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import boto3
from shared import settings

logger = logging.getLogger(__name__)


class FrameCaptioner:
    def __init__(
        self,
        *,
        client: Any | None = None,
        model_id: str | None = None,
        region: str | None = None,
    ) -> None:
        self.client = client or boto3.client(
            "bedrock-runtime", region_name=region or settings.aws_region
        )
        self.model_id = model_id or settings.bedrock_llm_model_id

    def caption(self, image_path: Path) -> str:
        image_bytes = image_path.read_bytes()
        response = self.client.converse(
            modelId=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": "jpeg",
                                "source": {"bytes": image_bytes},
                            },
                        },
                        {"text": _CAPTION_PROMPT},
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 150, "temperature": 0.1},
        )
        parts = response.get("output", {}).get("message", {}).get("content", [])
        text = "".join(str(p.get("text", "")) for p in parts).strip()
        if not text:
            logger.warning("empty_caption image=%s", image_path.name)
            return f"Video frame from {image_path.stem}"
        return text

    def caption_frames(self, image_paths: list[Path]) -> list[str]:
        captions: list[str] = []
        for path in image_paths:
            try:
                captions.append(self.caption(path))
            except Exception:
                logger.exception("caption_error image=%s", path.name)
                captions.append(f"Video frame from {path.stem}")
        return captions


_CAPTION_PROMPT = (
    "Describe this video frame in 1-2 sentences. "
    "Focus on what is visible: people, objects, text on screen, "
    "diagrams, slides, or actions being performed. Be specific and factual."
)
