"""Grounded answer generation with Bedrock."""

from __future__ import annotations

from typing import Any, Protocol

import boto3
from shared import settings


class AnswerGenerator(Protocol):
    def generate(self, *, query: str, context: str, intent: str | None = None) -> str: ...
    def rewrite_query(self, *, query: str) -> str: ...


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

    def generate(self, *, query: str, context: str, intent: str | None = None) -> str:
        return self._invoke(
            prompt=_prompt(query=query, context=context, intent=intent),
            max_tokens=450,
            temperature=0.1,
        )

    def rewrite_query(self, *, query: str) -> str:
        return self._invoke(
            prompt=_rewrite_prompt(query=query),
            max_tokens=150,
            temperature=0.3,
        )

    def _invoke(self, *, prompt: str, max_tokens: int, temperature: float) -> str:
        response = self.client.converse(
            modelId=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        return _extract_text(response).strip()


def _prompt(*, query: str, context: str, intent: str | None = None) -> str:
    visual_rules = ""
    if intent == "visual":
        visual_rules = (
            '- Evidence labeled "visual_caption" contains AI-generated frame descriptions. '
            "These are approximate — treat them as strong evidence when they describe the "
            "same scene the user asks about, even if exact wording differs.\n"
            "- For visual queries, if any context entry describes a matching scene, confirm "
            "the match and cite the timestamp. Do NOT refuse.\n"
        )

    return f"""You answer questions over indexed video evidence.

Rules:
- Use only the evidence in CONTEXT.
- Cite timestamps naturally, for example "around 1:15".
{visual_rules}- If the context is weak or unrelated, say:
  "I could not find strong evidence for that in the indexed videos."
- Be concise: 2-4 sentences.

QUESTION:
{query}

CONTEXT:
{context}

ANSWER:
"""


def _rewrite_prompt(*, query: str) -> str:
    return (
        "Given this search query about a video, write a short passage (2-3 sentences) "
        "that a video transcript might contain if it answered this question. "
        "Write it as if quoting the transcript, not as a direct answer.\n"
        "Return only the passage, no preamble.\n\n"
        f"QUERY:\n{query}\n"
    )


def _extract_text(response: dict[str, Any]) -> str:
    parts = response.get("output", {}).get("message", {}).get("content", [])
    text = "".join(str(part.get("text", "")) for part in parts)
    if not text:
        raise RuntimeError("Bedrock response did not include output text")
    return text
