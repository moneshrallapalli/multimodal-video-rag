"""Deterministic metric tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("eval").resolve()))

from metrics import score_query, summarize_scores  # noqa: E402
from schema import GoldenQuery  # noqa: E402
from shared.schemas import SearchResponse, SearchResult  # noqa: E402


def _result(start: float, end: float, modality: str = "transcript") -> SearchResult:
    return SearchResult(
        rank=1,
        video_id="vid",
        title="Video",
        start_seconds=start,
        end_seconds=end,
        modality=modality,
        score=0.9,
        snippet="snippet",
        thumbnail_url="https://example.com/thumb.jpg",
        seek_url="https://youtu.be/12345678901?t=1",
    )


def test_score_query_detects_relevant_timestamp_and_modality():
    row = GoldenQuery(
        id="q1",
        query="where",
        type="transcript",
        video_id="vid",
        relevant_timestamps=[(10, 20)],
        expected_modality="transcript",
        reference_answer="answer",
    )
    response = SearchResponse(
        query="where",
        intent="transcript",
        answer="answer",
        confidence=0.8,
        results=[_result(12, 18)],
    )

    score = score_query(row, response)

    assert score.recall_at_5 == 1.0
    assert score.recall_at_10 == 1.0
    assert score.mrr == 1.0
    assert score.timestamp_at_5s == 1.0
    assert score.modality_correct is True


def test_score_query_can_evaluate_unfiltered_expected_video():
    row = GoldenQuery(
        id="q-unfiltered",
        query="where is the sprint review feedback?",
        type="transcript",
        video_id=None,
        expected_video_id="expected-video",
        relevant_timestamps=[(10, 20)],
        expected_modality="transcript",
        reference_answer="answer",
    )
    response = SearchResponse(
        query="where is the sprint review feedback?",
        intent="transcript",
        answer="answer",
        confidence=0.8,
        results=[
            _result(12, 18).model_copy(update={"video_id": "other-video"}),
            _result(12, 18).model_copy(update={"video_id": "expected-video", "rank": 2}),
        ],
    )

    score = score_query(row, response)

    assert score.recall_at_5 == 1.0
    assert score.mrr == 0.5


def test_score_query_tracks_no_answer_confusion():
    no_answer = GoldenQuery(
        id="q2",
        query="weather",
        type="no_answer",
        video_id="vid",
        relevant_timestamps=[],
        expected_modality="none",
        reference_answer=None,
    )
    answerable = GoldenQuery(
        id="q3",
        query="where",
        type="visual",
        video_id="vid",
        relevant_timestamps=[(0, 0)],
        expected_modality="visual",
        reference_answer="answer",
    )

    scores = [
        score_query(
            no_answer,
            SearchResponse(query="weather", intent="no_answer", refused=True, confidence=0),
        ),
        score_query(
            answerable,
            SearchResponse(
                query="where", intent="visual", refused=False, confidence=0.7, results=[]
            ),
        ),
    ]

    summary = summarize_scores(scores)

    assert summary["no_answer"]["true_positive"] == 1
    assert summary["no_answer"]["true_negative"] == 1
    assert summary["no_answer"]["precision"] == 1.0
    assert summary["no_answer"]["recall"] == 1.0
