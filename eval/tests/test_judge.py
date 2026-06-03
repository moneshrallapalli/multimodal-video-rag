"""LLM judge parsing and summary tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("eval").resolve()))

from judge import parse_judge_json, summarize_judgments  # noqa: E402


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
