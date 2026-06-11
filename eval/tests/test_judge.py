"""LLM judge parsing and summary tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("eval").resolve()))

from judge import HaikuAnswerJudge, parse_judge_json, summarize_judgments  # noqa: E402
from schema import GoldenQuery  # noqa: E402
from shared.schemas import SearchResponse  # noqa: E402


def test_haiku_judge_prompt_calibrates_timestamp_tolerance():
    """Evidence chunks span tens of seconds; the judge must not fail an answer
    whose cited span brackets the reference moment."""

    class FakeBedrock:
        def __init__(self) -> None:
            self.calls = []

        def converse(self, **kwargs):
            self.calls.append(kwargs)
            text = '{"score": 1, "grounded": true, "correct": true, "useful": true}'
            return {"output": {"message": {"content": [{"text": text}]}}}

    client = FakeBedrock()
    judge = HaikuAnswerJudge(client=client, model_id="model-id")
    row = GoldenQuery(
        id="q1",
        query="When is the book mentioned?",
        type="timestamp",
        expected_modality="transcript",
        reference_answer="Around 1:16-1:28.",
    )
    response = SearchResponse(
        query=row.query, intent="timestamp", answer="Around 1:14-1:45.", confidence=0.5
    )

    judgment = judge.score(row, response)

    assert judgment["correct"] is True
    prompt = client.calls[0]["messages"][0]["content"][0]["text"]
    assert "wider span that brackets the reference timestamp" in prompt


def test_parse_judge_json_extracts_object_from_text():
    parsed = parse_judge_json(
        'Here is the grade: {"score": 0.75, "grounded": true, '
        '"correct": false, "useful": true, "rationale": "mostly useful"}'
    )

    assert parsed["score"] == 0.75
    assert parsed["grounded"] is True
    assert parsed["correct"] is False


def test_summarize_judgments_averages_boolean_rates():
    summary = summarize_judgments(
        [
            {"score": 1.0, "grounded": True, "correct": True, "useful": True},
            {"score": 0.5, "grounded": True, "correct": False, "useful": True},
        ]
    )

    assert summary == {
        "n": 2,
        "answer_quality": 0.75,
        "grounded_rate": 1.0,
        "correct_rate": 0.5,
        "useful_rate": 1.0,
    }
