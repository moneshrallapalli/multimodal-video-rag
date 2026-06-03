"""Public search service wiring.

Configured environments use the real Phase 4 LangGraph pipeline. Lightweight
local/test environments without vector/LLM credentials keep the Phase 1 mock
shape so the frontend can still run.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from graph import QueryPipeline
from graph.models import GraphConfig
from shared import settings
from shared.bm25 import BM25Encoder
from shared.schemas import SearchRequest, SearchResponse

from .mock_data import NO_ANSWER_MESSAGE, mock_search
from .reranking import LambdaCrossEncoderReranker

logger = logging.getLogger("video_rag.api.search")


def search_videos(req: SearchRequest) -> SearchResponse:
    if not real_search_enabled():
        return mock_search(req)
    try:
        return _pipeline().run(req)
    except Exception:
        # Surface the underlying error to CloudWatch so a real pipeline failure
        # (Pinecone outage, Bedrock throttling, etc.) is distinguishable from a
        # legitimate weak-evidence refusal on the dashboard. The metric filter on
        # `search_pipeline_error` log lines counts these.
        logger.exception(
            "search_pipeline_error query_len=%s video_id=%s",
            len(req.query),
            req.video_id or "",
        )
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
    return QueryPipeline(
        config=_graph_config(),
        transcript_bm25_resolver=_bm25_encoder,
        cross_encoder_reranker=_cross_encoder_reranker(),
    )


def _graph_config() -> GraphConfig:
    enable_cross_encoder_rerank = settings.enable_cross_encoder_rerank
    if enable_cross_encoder_rerank and not settings.cross_encoder_reranker_function_name:
        logger.warning("cross_encoder_rerank_disabled_no_remote")
        enable_cross_encoder_rerank = False
    return GraphConfig(
        enable_hybrid_transcript=settings.enable_hybrid_transcript,
        enable_cross_encoder_rerank=enable_cross_encoder_rerank,
        enable_query_rewrite=settings.enable_query_rewrite,
        hybrid_alpha=settings.hybrid_alpha,
    )


@lru_cache(maxsize=128)
def _bm25_encoder(video_id: str | None) -> BM25Encoder | None:
    if not settings.s3_bucket:
        logger.warning("bm25_disabled_no_s3_bucket video_id=%s", video_id or "")
        return None
    if not video_id:
        corpus_encoder = BM25Encoder.load_corpus_from_s3(bucket=settings.s3_bucket)
        if corpus_encoder is None:
            logger.warning("bm25_corpus_stats_missing")
        return corpus_encoder
    encoder = BM25Encoder.load_from_s3(bucket=settings.s3_bucket, video_id=video_id)
    if encoder is None:
        logger.warning("bm25_stats_missing video_id=%s", video_id)
    return encoder


@lru_cache
def _cross_encoder_reranker() -> LambdaCrossEncoderReranker | None:
    if not settings.cross_encoder_reranker_function_name:
        return None
    return LambdaCrossEncoderReranker(
        function_name=settings.cross_encoder_reranker_function_name,
    )
