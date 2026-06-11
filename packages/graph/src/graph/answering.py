"""Grounded answer generation with Bedrock."""

from __future__ import annotations

import json
import logging
from typing import Any, NamedTuple, Protocol

import boto3
from shared import settings

logger = logging.getLogger("video_rag.graph.answering")


class GeneratedAnswer(NamedTuple):
    """Structured answer: the text plus the model's own grounding judgment.

    `grounded=False` means the model judged the retrieved context too weak or
    unrelated to answer from — the pipeline propagates that as a refusal. This
    replaces the old substring matching on refusal phrases, which silently
    missed any paraphrase.
    """

    text: str
    grounded: bool


class AnswerGenerator(Protocol):
    def generate(
        self, *, query: str, context: str, intent: str | None = None
    ) -> GeneratedAnswer: ...
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

    def generate(self, *, query: str, context: str, intent: str | None = None) -> GeneratedAnswer:
        raw = self._invoke(
            prompt=_prompt(query=query, context=context, intent=intent),
            max_tokens=450,
            temperature=0.1,
        )
        return _parse_answer(raw)

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


def _parse_answer(raw: str) -> GeneratedAnswer:
    """Parse the model's JSON answer; tolerate code fences and stray prose.

    If no JSON object can be recovered, treat the whole text as a grounded
    answer (and log, so drift in the model's output format is observable on
    the dashboard rather than silently changing refusal behavior).
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    candidate = text
    if not candidate.startswith("{"):
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end > start:
            candidate = candidate[start : end + 1]
    try:
        payload = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        logger.warning("answer_parse_fallback len=%s", len(raw))
        return GeneratedAnswer(text=raw, grounded=True)
    if not isinstance(payload, dict) or not str(payload.get("answer") or "").strip():
        logger.warning("answer_parse_fallback len=%s", len(raw))
        return GeneratedAnswer(text=raw, grounded=True)
    return GeneratedAnswer(
        text=str(payload["answer"]).strip(),
        grounded=bool(payload.get("grounded", True)),
    )


def _prompt(*, query: str, context: str, intent: str | None = None) -> str:
    # Caption tolerance is unconditional: eval showed hybrid/timestamp questions
    # about visual content refuse just as often as visual-intent ones, so
    # restricting the leniency rules to intent == "visual" left most of the
    # over-refusals untouched.
    visual_rules = ""
    if intent == "visual":
        visual_rules = (
            "- For visual questions, if any context entry describes a matching scene, "
            'confirm the match, cite its timestamp, and set "grounded" to true.\n'
        )

    return f"""You answer questions over indexed video evidence.

Rules:
- Use only the evidence in CONTEXT.
- Cite timestamps naturally, for example "around 1:15". Context entries show
  their full time span (for example "3:48-4:20"); when asked when something
  happens, cite the span or the most specific moment the evidence supports,
  not just the span's start.
- Evidence labeled "visual_caption" contains AI-generated frame descriptions
  sampled every ~10 seconds. They are approximate: a caption describing the
  asked-about scene counts as evidence even if its wording differs, and an
  entry within about 15 seconds of an asked-about timestamp counts as
  evidence for that moment.
{visual_rules}- Partial evidence is still evidence: when the context answers part of the
  question, give that partial answer instead of refusing over missing detail.
  But related material on a different subject is not partial evidence: if the
  context never addresses the asked-about subject itself, do not repackage
  adjacent content as an answer.
- Be concise: 2-4 sentences. Exception: when the question asks for a list or
  a numbered set of items, enumerate every item the context contains, even if
  that runs longer.
- Respond with ONLY a JSON object, no other text:
  {{"answer": "<your answer>", "grounded": true}}
- "grounded" reports whether your answer states information from CONTEXT that
  addresses the question. If it does — even partially or approximately — set
  it to true. An answer that cites context timestamps as its support is
  grounded.
- Set "grounded" to false only when the context does not contain the
  information asked about (it is unrelated, or merely touches the topic
  without answering the question); then briefly say in "answer" that the
  indexed videos do not cover it.

QUESTION:
{query}

CONTEXT:
{context}

JSON:
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
