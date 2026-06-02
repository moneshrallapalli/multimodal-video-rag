"""Grounded answer generation with Bedrock."""

from __future__ import annotations

from typing import Any, Protocol

import boto3
from shared import settings


class AnswerGenerator(Protocol):
    def generate(self, *, query: str, context: str) -> str: ...


class BedrockAnswerGenerator:
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

    def generate(self, *, query: str, context: str) -> str:
        response = self.client.converse(
            modelId=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": _prompt(query=query, context=context)}],
                }
            ],
            inferenceConfig={"maxTokens": 450, "temperature": 0.1},
        )
        return _extract_text(response).strip()


def _prompt(*, query: str, context: str) -> str:
    return f"""You answer questions over indexed video evidence.

Rules:
- Use only the evidence in CONTEXT.
- Cite timestamps naturally, for example "around 1:15".
- If the context is weak or unrelated, say:
  "I could not find strong evidence for that in the indexed videos."
- Be concise: 2-4 sentences.

QUESTION:
{query}

CONTEXT:
{context}

ANSWER:
"""


def _extract_text(response: dict[str, Any]) -> str:
    parts = response.get("output", {}).get("message", {}).get("content", [])
    text = "".join(str(part.get("text", "")) for part in parts)
    if not text:
        raise RuntimeError("Bedrock response did not include output text")
    return text
