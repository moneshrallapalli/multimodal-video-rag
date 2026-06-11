"""Typed state for the LangGraph query pipeline.

The graph orchestrates: validate -> classify intent -> rewrite -> retrieve
(visual / transcript) -> fuse (RRF) -> rerank -> build context -> generate
(Bedrock) -> validate grounding -> respond. See the design docs.
"""

from __future__ import annotations

from typing import Literal, TypedDict

QueryIntent = Literal["visual", "transcript", "hybrid", "timestamp", "summary", "no_answer"]

# Which layer refused a query. Eval uses this to attribute over-refusals to the
# retrieval gate vs the LLM's grounded flag without sniffing answer text.
RefusalReason = Literal["empty_query", "retrieval_gate", "no_candidates", "llm_ungrounded"]


class Citation(TypedDict):
    video_id: str
    start_seconds: float
    end_seconds: float
    modality: str
    score: float


class GraphState(TypedDict, total=False):
    """State threaded through the query graph. `total=False` so nodes fill it
    incrementally."""

    query: str
    video_ids: list[str] | None
    top_k: int
    rewritten_query: str
    intent: QueryIntent
    errors: list[str]
    should_retrieve_transcript: bool
    should_retrieve_visual: bool
    visual_hits: list[dict]
    transcript_hits: list[dict]
    fused: list[dict]
    reranked: list[dict]
    context: str
    answer: str
    citations: list[Citation]
    grounding_score: float
    confidence: float
    refused: bool
    refusal_reason: RefusalReason
