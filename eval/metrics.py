"""Deterministic evaluation metrics for the video RAG seed set."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from schema import GoldenQuery
from shared.schemas import SearchResponse, SearchResult


@dataclass(frozen=True)
class QueryScore:
    id: str
    expected_no_answer: bool
    predicted_refused: bool
    recall_at_5: float
    recall_at_10: float
    mrr: float
    timestamp_at_5s: float
    timestamp_at_10s: float
    modality_correct: bool | None


def score_query(row: GoldenQuery, response: SearchResponse) -> QueryScore:
    expected_no_answer = row.expected_modality == "none" or row.type == "no_answer"
    if expected_no_answer:
        return QueryScore(
            id=row.id,
            expected_no_answer=True,
            predicted_refused=response.refused,
            recall_at_5=0.0,
            recall_at_10=0.0,
            mrr=0.0,
            timestamp_at_5s=0.0,
            timestamp_at_10s=0.0,
            modality_correct=None,
        )

    relevant_ranks = [
        index
        for index, result in enumerate(response.results, start=1)
        if result_matches(row, result, tolerance_seconds=10)
    ]
    first_relevant_rank = min(relevant_ranks, default=0)
    top = response.results[0] if response.results else None
    modality_correct = _modality_correct(row, response.results)
    return QueryScore(
        id=row.id,
        expected_no_answer=False,
        predicted_refused=response.refused,
        recall_at_5=1.0 if any(rank <= 5 for rank in relevant_ranks) else 0.0,
        recall_at_10=1.0 if any(rank <= 10 for rank in relevant_ranks) else 0.0,
        mrr=(1.0 / first_relevant_rank) if first_relevant_rank else 0.0,
        timestamp_at_5s=1.0 if top and result_matches(row, top, tolerance_seconds=5) else 0.0,
        timestamp_at_10s=1.0 if top and result_matches(row, top, tolerance_seconds=10) else 0.0,
        modality_correct=modality_correct,
    )


def summarize_scores(scores: list[QueryScore]) -> dict[str, Any]:
    answerable = [score for score in scores if not score.expected_no_answer]
    modality = [
        score.modality_correct for score in answerable if score.modality_correct is not None
    ]
    true_positive = sum(score.expected_no_answer and score.predicted_refused for score in scores)
    false_negative = sum(
        score.expected_no_answer and not score.predicted_refused for score in scores
    )
    false_positive = sum(
        (not score.expected_no_answer) and score.predicted_refused for score in scores
    )
    true_negative = sum(
        (not score.expected_no_answer) and not score.predicted_refused for score in scores
    )
    precision = _safe_div(true_positive, true_positive + false_positive)
    recall = _safe_div(true_positive, true_positive + false_negative)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return {
        "recall_at_5": _mean([score.recall_at_5 for score in answerable]),
        "recall_at_10": _mean([score.recall_at_10 for score in answerable]),
        "mrr": _mean([score.mrr for score in answerable]),
        "timestamp_at_5s": _mean([score.timestamp_at_5s for score in answerable]),
        "timestamp_at_10s": _mean([score.timestamp_at_10s for score in answerable]),
        "modality_acc": _mean([1.0 if value else 0.0 for value in modality]),
        "no_answer": {
            "true_positive": true_positive,
            "false_negative": false_negative,
            "false_positive": false_positive,
            "true_negative": true_negative,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
    }


def result_matches(
    row: GoldenQuery,
    result: SearchResult,
    *,
    tolerance_seconds: float,
) -> bool:
    expected_video_id = row.expected_video_id or row.video_id
    if expected_video_id and result.video_id != expected_video_id:
        return False
    for start, end in row.relevant_timestamps:
        expanded_start = start - tolerance_seconds
        expanded_end = end + tolerance_seconds
        result_start = result.start_seconds
        result_end = max(result.end_seconds, result.start_seconds)
        if result_start == result_end:
            if expanded_start <= result_start <= expanded_end:
                return True
        elif result_start <= expanded_end and result_end >= expanded_start:
            return True
    return False


def _modality_correct(row: GoldenQuery, results: list[SearchResult]) -> bool | None:
    if not results:
        return False
    if row.expected_modality == "visual":
        return results[0].modality in ("visual", "visual_caption")
    if row.expected_modality == "transcript":
        return results[0].modality == "transcript"
    if row.expected_modality == "hybrid":
        modalities = {result.modality for result in results[:5]}
        has_visual = bool(modalities & {"visual", "visual_caption"})
        return has_visual and "transcript" in modalities
    return None


def _mean(values: list[float]) -> float:
    return round(mean(values), 4) if values else 0.0


def _safe_div(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
