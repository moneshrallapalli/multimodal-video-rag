"""Retrieval helpers for Pinecone hits."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Protocol

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
_DEFAULT_CROSS_ENCODER_MODEL = "BAAI/bge-reranker-base"
_CROSS_ENCODER_MODEL: Any | None = None


class CrossEncoderReranker(Protocol):
    def predict(self, sentences: Sequence[tuple[str, str]]) -> Sequence[float]: ...


def transcript_candidate(hit: RetrievalHit, *, rank: int) -> RetrievalCandidate:
    metadata = hit.metadata
    video_id = str(metadata["video_id"])
    start = _float(metadata.get("start_seconds"), 0.0)
    end = _float(metadata.get("end_seconds"), start)
    text = str(metadata.get("text") or "")
    modality = str(metadata.get("modality") or "transcript")
    return RetrievalCandidate(
        id=hit.id,
        video_id=video_id,
        title=str(metadata.get("title") or "Indexed video"),
        modality=modality,
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
    # Prefer the frame's caption text: a contentless placeholder gives the
    # answer model an evidence pointer with nothing to ground on (a major
    # source of visual-question over-refusals).
    caption = str(metadata.get("text") or "")
    snippet = caption or f"Visual frame from {title} at {_mmss(timestamp)}."
    return RetrievalCandidate(
        id=hit.id,
        video_id=video_id,
        title=title,
        modality="visual",
        start_seconds=timestamp,
        end_seconds=timestamp,
        score=hit.score,
        snippet=snippet,
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


def cross_encoder_rerank(
    candidates: Sequence[RetrievalCandidate],
    *,
    query: str,
    reranker: CrossEncoderReranker | None = None,
) -> list[RetrievalCandidate]:
    """Use a cross-encoder to reorder fused candidates without changing scores."""

    if not candidates:
        return []

    model = reranker or _load_cross_encoder()
    pairs = [(query, _rerank_text(candidate)) for candidate in candidates]
    scores = [float(score) for score in model.predict(pairs)]
    scored = [
        (score, -index, candidate)
        for index, (score, candidate) in enumerate(zip(scores, candidates, strict=True))
    ]
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [
        candidate.model_copy(update={"rank": rank})
        for rank, (_, _, candidate) in enumerate(scored, start=1)
    ]


def max_source_score(candidates: Sequence[RetrievalCandidate]) -> float:
    return max((candidate.score for candidate in candidates), default=0.0)


def has_lexical_evidence(candidates: Sequence[RetrievalCandidate], *, query: str) -> bool:
    query_terms = _content_tokens(query)
    if not query_terms:
        return False

    query_phrase = " ".join(query_terms)
    for candidate in candidates:
        text_terms = _content_tokens(candidate.snippet)
        if not text_terms:
            continue

        text_phrase = " ".join(text_terms)
        if len(query_terms) > 1 and query_phrase in text_phrase:
            return True

        overlap = len(set(query_terms) & set(text_terms))
        if len(query_terms) <= 2 and overlap == len(query_terms):
            return True
        if 3 <= len(query_terms) <= 4 and overlap >= 2:
            return True
        if len(query_terms) >= 5 and overlap >= 3:
            return True

    return False


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


def _load_cross_encoder() -> Any:
    global _CROSS_ENCODER_MODEL

    if _CROSS_ENCODER_MODEL is None:
        from sentence_transformers import CrossEncoder

        _CROSS_ENCODER_MODEL = CrossEncoder(_DEFAULT_CROSS_ENCODER_MODEL)
    return _CROSS_ENCODER_MODEL


def _rerank_text(candidate: RetrievalCandidate) -> str:
    return (
        f"Title: {candidate.title}\n"
        f"Modality: {candidate.modality}\n"
        f"Timestamp: {_mmss(candidate.start_seconds)}\n"
        f"Evidence: {candidate.snippet}"
    )


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
