"""Retrieval helpers for Pinecone hits."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from shared.schemas import RetrievalHit

from .models import RetrievalCandidate, seek_url, thumbnail_url

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "around",
    "ask",
    "asked",
    "before",
    "does",
    "find",
    "from",
    "how",
    "into",
    "she",
    "show",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "video",
    "what",
    "when",
    "where",
    "with",
}


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


def lexical_rerank(
    candidates: Sequence[RetrievalCandidate],
    *,
    query: str,
) -> list[RetrievalCandidate]:
    """Nudge exact transcript matches above merely-near semantic neighbors."""

    query_terms = _content_tokens(query)
    if not query_terms:
        return [
            candidate.model_copy(update={"rank": rank})
            for rank, candidate in enumerate(candidates, start=1)
        ]

    scored = [
        (
            _combined_rerank_score(candidate, query_terms=query_terms),
            index,
            candidate,
        )
        for index, candidate in enumerate(candidates)
    ]
    scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    return [
        candidate.model_copy(update={"rank": rank})
        for rank, (_, _, candidate) in enumerate(scored, start=1)
    ]


def max_source_score(candidates: Sequence[RetrievalCandidate]) -> float:
    return max((candidate.score for candidate in candidates), default=0.0)


def _combined_rerank_score(
    candidate: RetrievalCandidate,
    *,
    query_terms: list[str],
) -> float:
    text_terms = _content_tokens(f"{candidate.title} {candidate.snippet}")
    if not text_terms:
        return candidate.score
    text_set = set(text_terms)
    overlap = sum(1 for term in query_terms if term in text_set) / len(query_terms)
    query_bigrams = set(zip(query_terms, query_terms[1:], strict=False))
    text_bigrams = set(zip(text_terms, text_terms[1:], strict=False))
    bigram_overlap = len(query_bigrams & text_bigrams)
    phrase_bonus = 0.04 if " ".join(query_terms) in " ".join(text_terms) else 0.0
    return candidate.score + (0.05 * overlap) + (0.025 * bigram_overlap) + phrase_bonus


def _content_tokens(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall(text.lower())
        if len(token) > 2 and token not in _STOPWORDS
    ]


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mmss(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"
