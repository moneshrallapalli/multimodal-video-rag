"""Optional LLM judge for answer quality evaluation."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from statistics import mean
from typing import Any, Protocol

import boto3
from schema import GoldenQuery
from shared import settings
from shared.schemas import SearchResponse


class AnswerJudge(Protocol):
    def score(self, row: GoldenQuery, response: SearchResponse) -> dict[str, Any]: ...


class HaikuAnswerJudge:
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

    def score(self, row: GoldenQuery, response: SearchResponse) -> dict[str, Any]:
        answer = response.answer or ""
        evidence = "\n".join(
            f"- {result.title} @ {result.start_seconds:.1f}s [{result.modality}]: "
            f"{result.snippet[:400]}"
            for result in response.results[:5]
        )
        prompt = _judge_prompt(
            question=row.query,
            reference=row.reference_answer or "",
            answer=answer,
            evidence=evidence,
        )
        raw = self.client.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 220, "temperature": 0.0},
        )
        text = _extract_text(raw)
        parsed = parse_judge_json(text)
        return {
            "score": float(parsed["score"]),
            "grounded": bool(parsed["grounded"]),
            "correct": bool(parsed["correct"]),
            "useful": bool(parsed["useful"]),
            "rationale": str(parsed.get("rationale", ""))[:500],
        }


def summarize_judgments(judgments: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not judgments:
        return {
            "n": 0,
            "answer_quality": 0.0,
            "grounded_rate": 0.0,
            "correct_rate": 0.0,
            "useful_rate": 0.0,
        }
    return {
        "n": len(judgments),
        "answer_quality": round(mean(float(item["score"]) for item in judgments), 4),
        "grounded_rate": round(mean(1.0 if item["grounded"] else 0.0 for item in judgments), 4),
        "correct_rate": round(mean(1.0 if item["correct"] else 0.0 for item in judgments), 4),
        "useful_rate": round(mean(1.0 if item["useful"] else 0.0 for item in judgments), 4),
    }


def parse_judge_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise RuntimeError("Judge response did not contain JSON")
    data = json.loads(match.group(0))
    for key in ("score", "grounded", "correct", "useful"):
        if key not in data:
            raise RuntimeError(f"Judge response missing {key}")
    return data


def _judge_prompt(*, question: str, reference: str, answer: str, evidence: str) -> str:
    return f"""Grade a video RAG answer.

Return JSON only with:
- score: number from 0 to 1
- grounded: boolean, true if the answer is supported by the evidence
- correct: boolean, true if it matches the reference answer. Timestamp
  citations: evidence chunks span tens of seconds, so a cited time or span
  matches when it contains or falls within about 15 seconds of the reference
  moment. Never mark an answer incorrect solely because its citation is a
  wider span that brackets the reference timestamp.
- useful: boolean, true if it would help the user
- rationale: one short sentence

QUESTION:
{question}

REFERENCE ANSWER:
{reference}

MODEL ANSWER:
{answer}

RETRIEVED EVIDENCE:
{evidence}
"""


def _extract_text(response: dict[str, Any]) -> str:
    parts = response.get("output", {}).get("message", {}).get("content", [])
    text = "".join(str(part.get("text", "")) for part in parts)
    if not text:
        raise RuntimeError("Judge response did not include text")
    return text
