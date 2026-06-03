"""Internal models for the Phase 4 query graph."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CandidateModality = Literal["visual", "transcript"]


class RetrievalCandidate(BaseModel):
    id: str
    video_id: str
    title: str
    modality: CandidateModality
    start_seconds: float
    end_seconds: float
    score: float
    snippet: str
    thumbnail_url: str
    seek_url: str
    s3_uri: str | None = None
    rank: int = 0


class GraphConfig(BaseModel):
    retrieve_top_k: int = 8
    rrf_k: int = 60
    # Legacy single-threshold gate. Kept for backwards compatibility with the
    # eval harness; prefer the per-modality thresholds below.
    min_source_score: float = 0.2
    # Per-modality refusal gates. Transcript index uses dotproduct, visual uses
    # cosine — their score distributions differ. A single threshold across both
    # produces modality-flip bugs at near-tied scores (see eval q006). Defaults
    # match the legacy 0.2 so behavior is identical until tuned.
    min_transcript_source_score: float = 0.2
    min_visual_source_score: float = 0.2
    # Confidence/display score = clamp(fused_RRF_score * confidence_scale, 0, 1).
    # The 24.0 default is empirically calibrated for rrf_k=60: at rank 1 the RRF
    # contribution from one list is 1/(60+1) ≈ 0.0164, so a candidate that tops
    # both modality lists scores ≈ 0.033 → 0.79 displayed. If you change rrf_k,
    # rescale this too (rule of thumb: confidence_scale ≈ (rrf_k + 1) / 2.5).
    confidence_scale: float = 24.0
    # Hybrid transcript retrieval: dense Titan + sparse BM25 on the transcript
    # index. Off by default for back-compat with the dense baseline. When on, a
    # BM25Encoder must be passed to the pipeline; otherwise we silently fall
    # back to dense-only for that query.
    enable_hybrid_transcript: bool = False
    # alpha=1 → pure dense, alpha=0 → pure sparse. 0.7 is Pinecone's documented
    # default starting point; tune empirically via the eval harness.
    hybrid_alpha: float = 0.7
    # Cross-encoder reranking is CPU-heavy and requires sentence-transformers, so
    # keep it opt-in and bake the model into the API container image.
    enable_cross_encoder_rerank: bool = False
    # Optional Haiku query rewrite used by the ablation harness. Off by default
    # so the dense baseline keeps the original query path.
    enable_query_rewrite: bool = False
    # Rewrite is most useful for terse queries. Already-specific queries often
    # lose exact lexical anchors when rewritten, so skip them above this limit.
    query_rewrite_max_terms: int = 3
    # Eval can disable generation when it only needs retrieval metrics. The API
    # keeps this on so user-facing answers still come from Bedrock.
    enable_answer_generation: bool = True
    no_answer_message: str = (
        "I could not find strong evidence for that in the indexed videos. "
        "Try a more specific visual description or search within a single video."
    )


def thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def seek_url(video_id: str, seconds: float) -> str:
    return f"https://youtu.be/{video_id}?t={int(seconds)}"
