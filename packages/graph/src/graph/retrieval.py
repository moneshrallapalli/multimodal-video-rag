"""Retrieval helpers for Pinecone hits."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from shared.schemas import RetrievalHit

from .models import RetrievalCandidate, seek_url, thumbnail_url


def transcript_candidate(hit: RetrievalHit, *, rank: int) -> RetrievalCandidate:
    metadata = hit.metadata
    video_id = str(metadata["video_id"])
    start = _float(metadata.get("start_seconds"), 0.0)
    end = _float(metadata.get("end_seconds"), start)
    text = str(metadata.get("text") or "")
    return RetrievalCandidate(
        id=hit.id,
        video_id=video_id,
        title=str(metadata.get("title") or "Indexed video"),
        modality="transcript",
        start_seconds=start,
        end_seconds=end,
        score=hit.score,
        snippet=text,
        thumbnail_url=thumbnail_url(video_id),
        seek_url=seek_url(video_id, start),
        rank=rank,
    )


def visual_candidate(hit: RetrievalHit, *, rank: int) -> RetrievalCandidate:
    metadata = hit.metadata
    video_id = str(metadata["video_id"])
    timestamp = _float(metadata.get("timestamp_seconds"), 0.0)
    s3_uri = str(metadata.get("s3_uri") or "")
    title = str(metadata.get("title") or "Indexed video")
    return RetrievalCandidate(
        id=hit.id,
        video_id=video_id,
        title=title,
        modality="visual",
        start_seconds=timestamp,
        end_seconds=timestamp,
        score=hit.score,
        snippet=f"Visual frame from {title} at {_mmss(timestamp)}.",
        thumbnail_url=thumbnail_url(video_id),
        seek_url=seek_url(video_id, timestamp),
        s3_uri=s3_uri or None,
        rank=rank,
    )


def reciprocal_rank_fusion(
    lists: Sequence[Sequence[RetrievalCandidate]],
    *,
    rrf_k: int = 60,
) -> list[RetrievalCandidate]:
    fused: dict[str, RetrievalCandidate] = {}
    scores: dict[str, float] = {}
    best_source_scores: dict[str, float] = {}

    for candidates in lists:
        for rank, candidate in enumerate(candidates, start=1):
            if candidate.id not in fused:
                fused[candidate.id] = candidate
                scores[candidate.id] = 0.0
                best_source_scores[candidate.id] = candidate.score
            scores[candidate.id] += 1.0 / (rrf_k + rank)
            best_source_scores[candidate.id] = max(
                best_source_scores[candidate.id], candidate.score
            )

    results: list[RetrievalCandidate] = []
    for candidate_id, candidate in fused.items():
        results.append(candidate.model_copy(update={"score": scores[candidate_id]}))
    results.sort(
        key=lambda candidate: (candidate.score, best_source_scores[candidate.id]), reverse=True
    )
    return [
        candidate.model_copy(update={"rank": rank})
        for rank, candidate in enumerate(results, start=1)
    ]


def max_source_score(candidates: Sequence[RetrievalCandidate]) -> float:
    return max((candidate.score for candidate in candidates), default=0.0)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mmss(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"
