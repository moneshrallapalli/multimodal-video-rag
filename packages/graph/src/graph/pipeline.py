"""LangGraph query pipeline for Phase 4 retrieval."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph
from shared import settings
from shared.bm25 import BM25Encoder
from shared.embedding import BedrockEmbedder
from shared.pinecone_client import PineconeIndexClient, hybrid_blend
from shared.schemas import QueryIntent, SearchRequest, SearchResponse, SearchResult

from .answering import AnswerGenerator, BedrockAnswerGenerator
from .models import GraphConfig, RetrievalCandidate
from .retrieval import (
    CrossEncoderReranker,
    cross_encoder_rerank,
    has_lexical_evidence,
    lexical_rerank,
    max_source_score,
    reciprocal_rank_fusion,
    transcript_candidate,
    visual_candidate,
)
from .state import GraphState

_VISUAL_KEYWORDS = {
    "show",
    "see",
    "shown",
    "look",
    "image",
    "frame",
    "slide",
    "screen",
    "whiteboard",
    "diagram",
    "visual",
    "desk",
}
_TRANSCRIPT_KEYWORDS = {
    "say",
    "said",
    "explain",
    "explains",
    "mention",
    "mentions",
    "talk",
    "talks",
    "discuss",
    "describe",
}
_SUMMARY_KEYWORDS = {"summary", "summarize", "summarise", "takeaway", "takeaways", "lessons"}
_TIMESTAMP_KEYWORDS = {"when", "timestamp", "minute", "second"}
_OFF_DOMAIN = {"weather", "recipe", "stock", "stocks", "bitcoin", "football", "lottery", "pizza"}

logger = logging.getLogger("video_rag.graph")


class QueryPipeline:
    def __init__(
        self,
        *,
        embedder: BedrockEmbedder | None = None,
        transcript_index: Any | None = None,
        visual_index: Any | None = None,
        answer_generator: AnswerGenerator | None = None,
        config: GraphConfig | None = None,
        transcript_bm25: BM25Encoder | None = None,
        transcript_bm25_resolver: Callable[[str | None], BM25Encoder | None] | None = None,
        cross_encoder_reranker: CrossEncoderReranker | None = None,
    ) -> None:
        self.embedder = embedder or BedrockEmbedder()
        self.transcript_index = transcript_index or PineconeIndexClient.from_index_name(
            settings.pinecone_transcript_index,
            expected_dim=settings.embed_dim,
            expected_metric="dotproduct",
        )
        self.visual_index = visual_index or PineconeIndexClient.from_index_name(
            settings.pinecone_visual_index,
            expected_dim=settings.embed_dim,
            expected_metric="cosine",
        )
        self.answer_generator = answer_generator or BedrockAnswerGenerator()
        self.config = config or GraphConfig()
        # When a BM25 encoder is provided AND `config.enable_hybrid_transcript`
        # is set, transcript queries blend dense + sparse via Pinecone hybrid.
        # Otherwise we fall back to dense-only — the same behavior as before.
        self.transcript_bm25 = transcript_bm25
        self.transcript_bm25_resolver = transcript_bm25_resolver
        self.cross_encoder_reranker = cross_encoder_reranker
        self.graph = self._build_graph()

    def run(self, request: SearchRequest) -> SearchResponse:
        state = self.graph.invoke(
            {
                "query": request.query.strip(),
                "video_id": request.video_id,
                "top_k": request.top_k,
                "errors": [],
            }
        )
        return self._to_search_response(state)

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("validate_query", self._validate_query)
        graph.add_node("classify_intent", self._classify_intent)
        graph.add_node("rewrite_query", self._rewrite_query)
        graph.add_node("retrieve_transcript", self._retrieve_transcript)
        graph.add_node("retrieve_visual", self._retrieve_visual)
        graph.add_node("fuse_results", self._fuse_results)
        graph.add_node("apply_retrieval_gate", self._apply_retrieval_gate)
        graph.add_node("build_context", self._build_context)
        graph.add_node("generate_answer", self._generate_answer)
        graph.set_entry_point("validate_query")
        graph.add_edge("validate_query", "classify_intent")
        graph.add_edge("classify_intent", "rewrite_query")
        graph.add_edge("rewrite_query", "retrieve_transcript")
        graph.add_edge("retrieve_transcript", "retrieve_visual")
        graph.add_edge("retrieve_visual", "fuse_results")
        graph.add_edge("fuse_results", "apply_retrieval_gate")
        graph.add_edge("apply_retrieval_gate", "build_context")
        graph.add_edge("build_context", "generate_answer")
        graph.add_edge("generate_answer", END)
        return graph.compile()

    def _validate_query(self, state: GraphState) -> GraphState:
        query = state.get("query", "").strip()
        if not query:
            return {"refused": True, "answer": self.config.no_answer_message, "confidence": 0.0}
        return {"query": query}

    def _classify_intent(self, state: GraphState) -> GraphState:
        query = state["query"].lower()
        tokens = set(query.replace("?", " ").replace(",", " ").split())
        if tokens & _OFF_DOMAIN:
            return {
                "intent": "no_answer",
                "refused": True,
                "answer": self.config.no_answer_message,
                "confidence": 0.0,
                "should_retrieve_transcript": False,
                "should_retrieve_visual": False,
            }
        if tokens & _SUMMARY_KEYWORDS:
            intent: QueryIntent = "summary"
            retrieve_transcript = True
            retrieve_visual = False
        elif tokens & _VISUAL_KEYWORDS and not tokens & _TRANSCRIPT_KEYWORDS:
            intent = "visual"
            retrieve_transcript = False
            retrieve_visual = True
        elif tokens & _TRANSCRIPT_KEYWORDS and not tokens & _VISUAL_KEYWORDS:
            intent = "transcript"
            retrieve_transcript = True
            retrieve_visual = False
        elif tokens & _TIMESTAMP_KEYWORDS:
            intent = "timestamp"
            retrieve_transcript = True
            retrieve_visual = True
        else:
            intent = "hybrid"
            retrieve_transcript = True
            retrieve_visual = True
        return {
            "intent": intent,
            "should_retrieve_transcript": retrieve_transcript,
            "should_retrieve_visual": retrieve_visual,
        }

    def _rewrite_query(self, state: GraphState) -> GraphState:
        if state.get("refused") or not self.config.enable_query_rewrite:
            return {}

        query = state["query"]
        try:
            rewritten = self.answer_generator.rewrite_query(query=query).strip()
        except Exception:
            logger.exception("query_rewrite_error query_len=%s", len(query))
            return {}

        if not rewritten:
            return {}
        return {"rewritten_query": rewritten}

    def _retrieve_transcript(self, state: GraphState) -> GraphState:
        if state.get("refused") or not state.get("should_retrieve_transcript"):
            return {"transcript_hits": []}
        query = _active_query(state)
        vector = self.embedder.embed_text(query)
        # Hybrid path: alpha-blend the dense vector with a BM25 sparse encoding
        # of the query. Falls through to pure dense when hybrid is disabled or
        # no BM25 encoder is configured (e.g. corpus not yet indexed).
        sparse_vector: dict[str, Any] | None = None
        query_vector = vector
        bm25_encoder = self._transcript_bm25_for(state.get("video_id"))
        if self.config.enable_hybrid_transcript and bm25_encoder is not None:
            sparse = bm25_encoder.encode_query(query)
            if sparse["indices"]:
                query_vector, sparse_vector = hybrid_blend(
                    vector, sparse, alpha=self.config.hybrid_alpha
                )
        hits = self.transcript_index.query(
            query_vector,
            top_k=self.config.retrieve_top_k,
            metadata_filter=_video_filter(state.get("video_id")),
            sparse_vector=sparse_vector,
        )
        return {
            "transcript_hits": [
                candidate.model_dump()
                for candidate in (
                    transcript_candidate(hit, rank=rank) for rank, hit in enumerate(hits, start=1)
                )
            ]
        }

    def _retrieve_visual(self, state: GraphState) -> GraphState:
        if state.get("refused") or not state.get("should_retrieve_visual"):
            return {"visual_hits": []}
        query = _active_query(state)
        vector = self.embedder.embed_visual_query(query)
        hits = self.visual_index.query(
            vector,
            top_k=self.config.retrieve_top_k,
            metadata_filter=_video_filter(state.get("video_id")),
        )
        return {
            "visual_hits": [
                candidate.model_dump()
                for candidate in (
                    visual_candidate(hit, rank=rank) for rank, hit in enumerate(hits, start=1)
                )
            ]
        }

    def _fuse_results(self, state: GraphState) -> GraphState:
        transcript = [_candidate(data) for data in state.get("transcript_hits", [])]
        visual = [_candidate(data) for data in state.get("visual_hits", [])]
        query = _active_query(state)
        fused = reciprocal_rank_fusion(
            [transcript, visual],
            rrf_k=self.config.rrf_k,
        )
        reranked = lexical_rerank(fused, query=query)
        if self.config.enable_cross_encoder_rerank:
            reranked = cross_encoder_rerank(
                reranked,
                query=query,
                reranker=self.cross_encoder_reranker,
            )
        reranked = reranked[: state.get("top_k", self.config.retrieve_top_k)]
        return {"fused": [candidate.model_dump() for candidate in reranked]}

    def _apply_retrieval_gate(self, state: GraphState) -> GraphState:
        if state.get("refused"):
            return {"fused": [], "confidence": 0.0}

        transcript_candidates = [_candidate(d) for d in state.get("transcript_hits", [])]
        visual_candidates = [_candidate(d) for d in state.get("visual_hits", [])]
        fused_candidates = [_candidate(data) for data in state.get("fused", [])]
        query = _active_query(state)

        # Per-modality dense gate (transcript uses dotproduct, visual uses cosine;
        # the score distributions differ, so a single threshold across both
        # produces modality-flip bugs at near-tied scores). Either modality
        # passing dense lets the answer proceed; lexical evidence stays as a
        # final safety net for terse queries.
        transcript_passes = max_source_score(transcript_candidates) >= (
            self.config.min_transcript_source_score
        )
        visual_passes = max_source_score(visual_candidates) >= (self.config.min_visual_source_score)
        has_dense_evidence = transcript_passes or visual_passes
        has_text_evidence = has_lexical_evidence(fused_candidates, query=query)

        if not fused_candidates or not (has_dense_evidence or has_text_evidence):
            return {
                "refused": True,
                "answer": self.config.no_answer_message,
                "confidence": 0.0,
                "fused": [],
            }
        top_score = max((candidate.score for candidate in fused_candidates), default=0.0)
        return {"confidence": _scale_to_unit(top_score, self.config.confidence_scale)}

    def _build_context(self, state: GraphState) -> GraphState:
        if state.get("refused"):
            return {"context": ""}
        lines = []
        for candidate in [_candidate(data) for data in state.get("fused", [])]:
            lines.append(
                f"[{candidate.rank}] {candidate.title} @ {_mmss(candidate.start_seconds)} "
                f"({candidate.modality}, score={candidate.score:.4f}): {candidate.snippet}"
            )
        return {"context": "\n".join(lines)}

    def _generate_answer(self, state: GraphState) -> GraphState:
        if state.get("refused"):
            return {}
        candidates = [_candidate(data) for data in state.get("fused", [])]
        if not candidates:
            return {"refused": True, "answer": self.config.no_answer_message, "confidence": 0.0}
        if all(candidate.modality == "visual" for candidate in candidates):
            return {"answer": _visual_answer(candidates[0]), "refused": False}
        try:
            answer = self.answer_generator.generate(
                query=_active_query(state),
                context=state.get("context", ""),
            )
        except Exception:
            # Bedrock throttling / network errors fall back to extractive answers
            # so the UX still works, but we log so the dashboard can count them
            # via the `bedrock_answer_error` metric filter (otherwise a real
            # outage is indistinguishable from a successful extractive path).
            logger.exception(
                "bedrock_answer_error query_len=%s candidates=%s",
                len(state.get("query", "")),
                len(candidates),
            )
            answer = _extractive_answer(candidates[0])
        return {"answer": answer, "refused": False}

    def _to_search_response(self, state: GraphState) -> SearchResponse:
        candidates = [_candidate(data) for data in state.get("fused", [])]
        return SearchResponse(
            query=state.get("query", ""),
            rewritten_query=state.get("rewritten_query"),
            intent=state.get("intent", "no_answer"),
            answer=state.get("answer") or self.config.no_answer_message,
            refused=bool(state.get("refused", False)),
            confidence=float(state.get("confidence", 0.0)),
            results=[
                SearchResult(
                    rank=rank,
                    video_id=candidate.video_id,
                    title=candidate.title,
                    start_seconds=candidate.start_seconds,
                    end_seconds=candidate.end_seconds,
                    modality=candidate.modality,
                    score=_scale_to_unit(candidate.score, self.config.confidence_scale),
                    snippet=candidate.snippet,
                    thumbnail_url=candidate.thumbnail_url,
                    seek_url=candidate.seek_url,
                )
                for rank, candidate in enumerate(candidates, start=1)
            ],
        )

    def _transcript_bm25_for(self, video_id: str | None) -> BM25Encoder | None:
        if self.transcript_bm25_resolver is not None:
            return self.transcript_bm25_resolver(video_id)
        return self.transcript_bm25


def _candidate(data: dict[str, Any]) -> RetrievalCandidate:
    return RetrievalCandidate.model_validate(data)


def _active_query(state: GraphState) -> str:
    return state.get("rewritten_query") or state["query"]


def _video_filter(video_id: str | None) -> dict[str, Any] | None:
    if not video_id:
        return None
    return {"video_id": {"$eq": video_id}}


def _mmss(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"


def _scale_to_unit(value: float, scale: float) -> float:
    """Clamp `value * scale` into [0, 1] with 3-decimal display precision."""
    return max(0.0, min(1.0, round(value * scale, 3)))


def _extractive_answer(top: RetrievalCandidate) -> str:
    return f"{top.snippet} This appears around {_mmss(top.start_seconds)} in “{top.title}”."


def _visual_answer(top: RetrievalCandidate) -> str:
    return f"The strongest visual match is around {_mmss(top.start_seconds)} in “{top.title}”."
