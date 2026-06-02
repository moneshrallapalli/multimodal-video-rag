"""Typed state for the LangGraph query pipeline.

The graph orchestrates: validate -> classify intent -> rewrite -> retrieve
(visual / transcript) -> fuse (RRF) -> rerank -> build context -> generate
(Bedrock) -> validate grounding -> respond. See the design docs.
"""
from __future__ import annotations

from typing import Literal, TypedDict

QueryIntent = Literal[
    "visual", "transcript", "hybrid", "timestamp", "summary", "no_answer"
]


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
    rewritten_query: str
    intent: QueryIntent
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
