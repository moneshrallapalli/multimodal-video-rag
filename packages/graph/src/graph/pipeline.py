"""LangGraph query pipeline for Phase 4 retrieval."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph
from shared import settings
from shared.embedding import BedrockEmbedder
from shared.pinecone_client import PineconeIndexClient
from shared.schemas import QueryIntent, SearchRequest, SearchResponse, SearchResult

from .answering import AnswerGenerator, BedrockAnswerGenerator
from .models import GraphConfig, RetrievalCandidate
from .retrieval import (
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


class QueryPipeline:
    def __init__(
        self,
        *,
        embedder: BedrockEmbedder | None = None,
        transcript_index: Any | None = None,
        visual_index: Any | None = None,
        answer_generator: AnswerGenerator | None = None,
        config: GraphConfig | None = None,
    ) -> None:
        self.embedder = embedder or BedrockEmbedder()
        self.transcript_index = transcript_index or PineconeIndexClient.from_index_name(
            settings.pinecone_transcript_index,
            expected_dim=settings.embed_dim,
        )
        self.visual_index = visual_index or PineconeIndexClient.from_index_name(
            settings.pinecone_visual_index,
            expected_dim=settings.embed_dim,
        )
        self.answer_generator = answer_generator or BedrockAnswerGenerator()
        self.config = config or GraphConfig()
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
        graph.add_node("retrieve_transcript", self._retrieve_transcript)
        graph.add_node("retrieve_visual", self._retrieve_visual)
        graph.add_node("fuse_results", self._fuse_results)
        graph.add_node("apply_retrieval_gate", self._apply_retrieval_gate)
        graph.add_node("build_context", self._build_context)
        graph.add_node("generate_answer", self._generate_answer)
        graph.set_entry_point("validate_query")
        graph.add_edge("validate_query", "classify_intent")
        graph.add_edge("classify_intent", "retrieve_transcript")
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

    def _retrieve_transcript(self, state: GraphState) -> GraphState:
        if state.get("refused") or not state.get("should_retrieve_transcript"):
            return {"transcript_hits": []}
        vector = self.embedder.embed_text(state["query"])
        hits = self.transcript_index.query(
            vector,
            top_k=self.config.retrieve_top_k,
            metadata_filter=_video_filter(state.get("video_id")),
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
        vector = self.embedder.embed_visual_query(state["query"])
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
        fused = reciprocal_rank_fusion(
            [transcript, visual],
            rrf_k=self.config.rrf_k,
        )[: state.get("top_k", self.config.retrieve_top_k)]
        return {"fused": [candidate.model_dump() for candidate in fused]}

    def _apply_retrieval_gate(self, state: GraphState) -> GraphState:
        if state.get("refused"):
            return {"fused": [], "confidence": 0.0}
        source_candidates = [
            *[_candidate(data) for data in state.get("transcript_hits", [])],
            *[_candidate(data) for data in state.get("visual_hits", [])],
        ]
        if (
            not state.get("fused")
            or max_source_score(source_candidates) < self.config.min_source_score
        ):
            return {
                "refused": True,
                "answer": self.config.no_answer_message,
                "confidence": 0.0,
                "fused": [],
            }
        top_score = max((_candidate(data).score for data in state.get("fused", [])), default=0.0)
        return {"confidence": min(1.0, round(top_score * 24, 3))}

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
        try:
            answer = self.answer_generator.generate(
                query=state["query"],
                context=state.get("context", ""),
            )
        except Exception:
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
                    score=max(0.0, min(1.0, round(candidate.score * 24, 3))),
                    snippet=candidate.snippet,
                    thumbnail_url=candidate.thumbnail_url,
                    seek_url=candidate.seek_url,
                )
                for rank, candidate in enumerate(candidates, start=1)
            ],
        )


def _candidate(data: dict[str, Any]) -> RetrievalCandidate:
    return RetrievalCandidate.model_validate(data)


def _video_filter(video_id: str | None) -> dict[str, Any] | None:
    if not video_id:
        return None
    return {"video_id": {"$eq": video_id}}


def _mmss(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"


def _extractive_answer(top: RetrievalCandidate) -> str:
    return f"{top.snippet} This appears around {_mmss(top.start_seconds)} in “{top.title}”."
