"""Public search service wiring.

Configured environments use the real Phase 4 LangGraph pipeline. Lightweight
local/test environments without vector/LLM credentials keep the Phase 1 mock
shape so the frontend can still run.
"""

from __future__ import annotations

from functools import lru_cache

from graph import QueryPipeline
from shared import settings
from shared.schemas import SearchRequest, SearchResponse

from .mock_data import NO_ANSWER_MESSAGE, mock_search


def search_videos(req: SearchRequest) -> SearchResponse:
    if not real_search_enabled():
        return mock_search(req)
    try:
        return _pipeline().run(req)
    except Exception:
        return SearchResponse(
            query=req.query,
            intent="no_answer",
            answer=NO_ANSWER_MESSAGE,
            refused=True,
            confidence=0.0,
            results=[],
        )


def real_search_enabled() -> bool:
    return bool(
        settings.pinecone_api_key
        and settings.pinecone_transcript_index
        and settings.pinecone_visual_index
        and settings.bedrock_llm_model_id
    )


@lru_cache
def _pipeline() -> QueryPipeline:
    return QueryPipeline()
