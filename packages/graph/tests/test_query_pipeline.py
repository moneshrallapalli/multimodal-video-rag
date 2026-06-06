"""Phase 4 query pipeline tests with fake service clients."""

from __future__ import annotations

from graph.models import GraphConfig, RetrievalCandidate
from graph.pipeline import QueryPipeline, _reorder_by_citations
from shared.schemas import RetrievalHit, SearchRequest


class FakeEmbedder:
    def __init__(self) -> None:
        self.text_queries: list[str] = []
        self.visual_queries: list[str] = []

    def embed_text(self, text: str) -> list[float]:
        self.text_queries.append(text)
        return [1.0, 0.0, 0.0]

    def embed_visual_query(self, text: str) -> list[float]:
        self.visual_queries.append(text)
        return [0.0, 1.0, 0.0]


class FakeIndex:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits
        self.calls = []

    def query(self, vector, *, top_k, metadata_filter=None, namespace=None, sparse_vector=None):
        self.calls.append(
            {
                "vector": vector,
                "top_k": top_k,
                "metadata_filter": metadata_filter,
                "namespace": namespace,
                "sparse_vector": sparse_vector,
            }
        )
        return self.hits


class FakeAnswerer:
    def __init__(
        self,
        answer: str = "Grounded answer with a timestamp around 1:15.",
        rewrite: str | None = None,
    ) -> None:
        self.answer = answer
        self.rewrite = rewrite
        self.calls = []
        self.rewrite_calls = []

    def generate(self, *, query: str, context: str, intent: str | None = None) -> str:
        self.calls.append({"query": query, "context": context, "intent": intent})
        return self.answer

    def rewrite_query(self, *, query: str) -> str:
        self.rewrite_calls.append(query)
        return self.rewrite or query


class FakeCrossEncoderReranker:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.calls = []

    def predict(self, pairs):
        self.calls.append(pairs)
        return self.scores


def _transcript_hit(score: float = 0.72) -> RetrievalHit:
    return RetrievalHit(
        id="QkdBXUikRQc:transcript:000004",
        score=score,
        metadata={
            "video_id": "QkdBXUikRQc",
            "chunk_id": "QkdBXUikRQc:transcript:000004",
            "start_seconds": 74.72,
            "end_seconds": 105,
            "title": "Stop Dreaming and Start Doing | Self-Sabotage",
            "text": "The speaker explains self-sabotaging behaviors and fear of failure.",
            "modality": "transcript",
        },
    )


def _visual_caption_hit(score: float = 0.55) -> RetrievalHit:
    return RetrievalHit(
        id="QkdBXUikRQc:caption:000001",
        score=score,
        metadata={
            "video_id": "QkdBXUikRQc",
            "chunk_id": "QkdBXUikRQc:caption:000001",
            "start_seconds": 0,
            "end_seconds": 0,
            "title": "Stop Dreaming and Start Doing | Self-Sabotage",
            "text": "Woman seated in a bedroom with wall art and bedside lamps.",
            "modality": "visual_caption",
        },
    )


def _visual_hit(score: float = 0.42) -> RetrievalHit:
    return RetrievalHit(
        id="QkdBXUikRQc:frame:000001",
        score=score,
        metadata={
            "video_id": "QkdBXUikRQc",
            "frame_id": "QkdBXUikRQc:frame:000001",
            "timestamp_seconds": 0,
            "title": "Stop Dreaming and Start Doing | Self-Sabotage",
            "modality": "visual",
            "s3_uri": "s3://bucket/videos/QkdBXUikRQc/frames/frame_000001.jpg",
        },
    )


def test_transcript_query_routes_to_transcript_index_only():
    embedder = FakeEmbedder()
    transcript = FakeIndex([_transcript_hit()])
    visual = FakeIndex([_visual_hit()])
    answerer = FakeAnswerer()
    pipeline = QueryPipeline(
        embedder=embedder,
        transcript_index=transcript,
        visual_index=visual,
        answer_generator=answerer,
    )

    response = pipeline.run(SearchRequest(query="Where do they explain self sabotage?"))

    assert response.refused is False
    assert response.answer == "Grounded answer with a timestamp around 1:15."
    assert response.intent == "transcript"
    assert response.results[0].modality == "transcript"
    assert response.results[0].start_seconds == 74.72
    assert embedder.text_queries == ["Where do they explain self sabotage?"]
    assert embedder.visual_queries == []
    assert len(transcript.calls) == 1
    assert visual.calls == []
    assert "self-sabotaging behaviors" in answerer.calls[0]["context"]


def test_visual_query_routes_to_both_indexes_with_video_filter():
    embedder = FakeEmbedder()
    transcript = FakeIndex([_visual_caption_hit()])
    visual = FakeIndex([_visual_hit()])
    answerer = FakeAnswerer()
    pipeline = QueryPipeline(
        embedder=embedder,
        transcript_index=transcript,
        visual_index=visual,
        answer_generator=answerer,
    )

    response = pipeline.run(
        SearchRequest(query="Show me the speaker at a desk", video_ids=["QkdBXUikRQc"])
    )

    assert response.refused is False
    assert response.intent == "visual"
    assert len(transcript.calls) == 1
    assert len(visual.calls) == 1
    assert visual.calls[0]["metadata_filter"] == {"video_id": {"$eq": "QkdBXUikRQc"}}
    modalities = {r.modality for r in response.results}
    assert modalities & {"visual", "visual_caption"}


def test_visual_query_retrieves_visual_captions():
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_visual_caption_hit(score=0.55)]),
        visual_index=FakeIndex([_visual_hit(score=0.30)]),
        answer_generator=FakeAnswerer(),
    )

    response = pipeline.run(
        SearchRequest(query="Show me a bedroom setting", video_ids=["QkdBXUikRQc"])
    )

    assert response.refused is False
    assert response.intent == "visual"
    caption_results = [r for r in response.results if r.modality == "visual_caption"]
    assert len(caption_results) >= 1
    assert "bedroom" in caption_results[0].snippet.lower()


def test_hybrid_query_fuses_both_modalities():
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit(score=0.5)]),
        visual_index=FakeIndex([_visual_hit(score=0.4)]),
        answer_generator=FakeAnswerer(),
    )

    response = pipeline.run(SearchRequest(query="self sabotage", top_k=2))

    assert response.refused is False
    assert response.intent == "hybrid"
    assert [result.modality for result in response.results] == ["transcript", "visual"]
    assert len(response.results) == 2


def test_exact_transcript_terms_rerank_above_semantic_neighbors():
    nearby = RetrievalHit(
        id="QkdBXUikRQc:transcript:nearby",
        score=0.72,
        metadata={
            "video_id": "QkdBXUikRQc",
            "start_seconds": 49.6,
            "end_seconds": 81.36,
            "title": "Stop Dreaming and Start Doing | Self-Sabotage",
            "text": "The speaker says fear and unfamiliar territory can be paralyzing.",
            "modality": "transcript",
        },
    )
    exact = RetrievalHit(
        id="QkdBXUikRQc:transcript:planning",
        score=0.6,
        metadata={
            "video_id": "QkdBXUikRQc",
            "start_seconds": 221.52,
            "end_seconds": 254.88,
            "title": "Stop Dreaming and Start Doing | Self-Sabotage",
            "text": (
                "The issue is that you're lacking proper planning. Instead of making big goals, "
                "cut them down into small, measurable steps."
            ),
            "modality": "transcript",
        },
    )
    answerer = FakeAnswerer(
        answer="Around 3:41, she says the issue is lacking proper planning.",
    )
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([nearby, exact]),
        visual_index=FakeIndex([_visual_hit(score=0.7)]),
        answer_generator=answerer,
    )

    response = pipeline.run(SearchRequest(query="What does she say about lacking proper planning?"))

    assert response.refused is False
    assert response.results[0].start_seconds == 221.52
    assert "lacking proper planning" in answerer.calls[0]["context"].splitlines()[0]


def test_answer_generation_can_be_disabled_for_retrieval_eval():
    answerer = FakeAnswerer(answer="Generated answer should not be used.")
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit()]),
        visual_index=FakeIndex([]),
        answer_generator=answerer,
        config=GraphConfig(enable_answer_generation=False),
    )

    response = pipeline.run(SearchRequest(query="Where do they explain self sabotage?"))

    assert response.refused is False
    assert response.answer.startswith("Top evidence is around 1:14")
    assert answerer.calls == []


def test_lexical_transcript_evidence_can_pass_low_dense_gate():
    planning = RetrievalHit(
        id="QkdBXUikRQc:transcript:planning",
        score=0.0879,
        metadata={
            "video_id": "QkdBXUikRQc",
            "start_seconds": 221.52,
            "end_seconds": 254.88,
            "title": "Stop Dreaming and Start Doing | Self-Sabotage",
            "text": (
                "The issue is that you're lacking proper planning. Instead of making big goals, "
                "cut them down into small, measurable steps."
            ),
            "modality": "transcript",
        },
    )
    answerer = FakeAnswerer()
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([planning]),
        visual_index=FakeIndex([]),
        answer_generator=answerer,
    )

    response = pipeline.run(SearchRequest(query="talk on proper planning"))

    assert response.refused is False
    assert response.results[0].start_seconds == 221.52
    assert "proper planning" in answerer.calls[0]["context"]


def test_off_domain_query_refuses_without_retrieval():
    transcript = FakeIndex([_transcript_hit()])
    visual = FakeIndex([_visual_hit()])
    answerer = FakeAnswerer()
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=transcript,
        visual_index=visual,
        answer_generator=answerer,
    )

    response = pipeline.run(SearchRequest(query="what is today's weather"))

    assert response.refused is True
    assert response.intent == "no_answer"
    assert response.results == []
    assert transcript.calls == []
    assert visual.calls == []
    assert answerer.calls == []


def test_low_score_retrieval_refuses():
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit(score=0.05)]),
        visual_index=FakeIndex([]),
        answer_generator=FakeAnswerer(),
    )

    response = pipeline.run(SearchRequest(query="Where do they explain self sabotage?"))

    assert response.refused is True
    assert response.results == []


def test_scale_to_unit_helper_and_default_confidence_calibration():
    """Pin the confidence/score scaling. Anyone tuning rrf_k must explicitly tune
    confidence_scale alongside, not discover it via drifting UI numbers."""
    from graph.models import GraphConfig
    from graph.pipeline import _scale_to_unit

    config = GraphConfig()
    assert config.confidence_scale == 24.0
    assert config.rrf_k == 60
    # RRF contribution at rank 1 from one list is 1/(60+1) ≈ 0.01639.
    # A candidate that tops *both* modality lists scores ≈ 0.03279.
    assert _scale_to_unit(1.0 / 61, config.confidence_scale) == 0.393
    assert _scale_to_unit(2.0 / 61, config.confidence_scale) == 0.787
    # Clamp behavior at both ends.
    assert _scale_to_unit(0.0, 24.0) == 0.0
    assert _scale_to_unit(1.0, 24.0) == 1.0
    assert _scale_to_unit(-0.1, 24.0) == 0.0


def test_hybrid_transcript_blends_dense_and_sparse_vectors_when_enabled():
    """When hybrid is enabled and an encoder is provided, the transcript query
    must send a `sparse_vector` to Pinecone (alpha-blended with the dense vector).
    When disabled, the query stays dense-only — preserving the v1 baseline."""
    from graph.models import GraphConfig
    from shared.bm25 import BM25Encoder

    encoder = BM25Encoder.fit(["sabotage is fear of starting", "comfort zone blocks growth"])
    transcript = FakeIndex([_transcript_hit()])
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=transcript,
        visual_index=FakeIndex([]),
        answer_generator=FakeAnswerer(),
        config=GraphConfig(enable_hybrid_transcript=True, hybrid_alpha=0.7),
        transcript_bm25=encoder,
    )

    pipeline.run(SearchRequest(query="fear of starting"))

    call = transcript.calls[0]
    assert call["sparse_vector"] is not None
    assert call["sparse_vector"]["indices"]
    assert call["sparse_vector"]["values"]


def test_hybrid_transcript_uses_bm25_resolver_for_video_filter():
    from graph.models import GraphConfig
    from shared.bm25 import BM25Encoder

    calls: list[str | None] = []
    encoder = BM25Encoder.fit(["sabotage is fear of starting", "comfort zone blocks growth"])
    transcript = FakeIndex([_transcript_hit()])
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=transcript,
        visual_index=FakeIndex([]),
        answer_generator=FakeAnswerer(),
        config=GraphConfig(enable_hybrid_transcript=True),
        transcript_bm25_resolver=lambda video_id: calls.append(video_id) or encoder,
    )

    pipeline.run(
        SearchRequest(query="Where do they explain self sabotage?", video_ids=["QkdBXUikRQc"])
    )

    assert calls == ["QkdBXUikRQc"]
    assert transcript.calls[0]["sparse_vector"] is not None


def test_hybrid_transcript_falls_back_to_dense_when_encoder_absent():
    """Toggling hybrid on without supplying a BM25 encoder must NOT blow up —
    we silently fall back to dense so the demo keeps working pre-deploy."""
    from graph.models import GraphConfig

    transcript = FakeIndex([_transcript_hit()])
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=transcript,
        visual_index=FakeIndex([]),
        answer_generator=FakeAnswerer(),
        config=GraphConfig(enable_hybrid_transcript=True),
        # transcript_bm25 deliberately omitted
    )

    pipeline.run(SearchRequest(query="self sabotage"))
    assert transcript.calls[0]["sparse_vector"] is None


def test_cross_encoder_rerank_reorders_fused_candidates_when_enabled():
    """The bge reranker is injected in tests so we never load the real model.
    It runs after fusion and before the retrieval gate, preserving candidate
    scores while updating rank order."""
    from graph.models import GraphConfig

    fake_reranker = FakeCrossEncoderReranker(scores=[0.1, 0.9])
    exact = _transcript_hit(score=0.4).model_copy(
        update={
            "id": "QkdBXUikRQc:transcript:exact",
            "metadata": {
                **_transcript_hit(score=0.4).metadata,
                "chunk_id": "QkdBXUikRQc:transcript:exact",
                "text": "The speaker explains self sabotage and fear of failure.",
            },
        }
    )
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit(score=0.5), exact]),
        visual_index=FakeIndex([_visual_hit(score=0.4)]),
        answer_generator=FakeAnswerer(),
        config=GraphConfig(enable_cross_encoder_rerank=True),
        cross_encoder_reranker=fake_reranker,
    )

    response = pipeline.run(SearchRequest(query="Where do they explain self sabotage?", top_k=2))

    assert len(fake_reranker.calls) == 1
    assert len(fake_reranker.calls[0]) == 2
    assert response.results[0].snippet == "The speaker explains self sabotage and fear of failure."
    assert response.results[0].rank == 1


def test_cross_encoder_rerank_fires_on_visual_intent_with_mixed_modalities():
    from graph.models import GraphConfig

    fake_reranker = FakeCrossEncoderReranker(scores=[1.0, 0.5])
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit(score=0.5)]),
        visual_index=FakeIndex([_visual_hit(score=0.4)]),
        answer_generator=FakeAnswerer(),
        config=GraphConfig(enable_cross_encoder_rerank=True),
        cross_encoder_reranker=fake_reranker,
    )

    response = pipeline.run(SearchRequest(query="Show me the speaker at a desk", top_k=2))

    assert len(fake_reranker.calls) == 1
    assert response.refused is False


def test_cross_encoder_rerank_fires_on_mixed_modality_hybrid_intent():
    from graph.models import GraphConfig

    fake_reranker = FakeCrossEncoderReranker(scores=[0.2, 0.8])
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit(score=0.5)]),
        visual_index=FakeIndex([_visual_hit(score=0.5)]),
        answer_generator=FakeAnswerer(),
        config=GraphConfig(enable_cross_encoder_rerank=True),
        cross_encoder_reranker=fake_reranker,
    )

    response = pipeline.run(SearchRequest(query="self sabotage", top_k=2))

    assert response.intent == "hybrid"
    assert len(fake_reranker.calls) == 1


def test_hyde_uses_passage_for_embedding_but_original_query_for_answer():
    from graph.models import GraphConfig

    embedder = FakeEmbedder()
    hyde_passage = "self sabotage fear of failure planning"
    answerer = FakeAnswerer(rewrite=hyde_passage)
    pipeline = QueryPipeline(
        embedder=embedder,
        transcript_index=FakeIndex([_transcript_hit()]),
        visual_index=FakeIndex([]),
        answer_generator=answerer,
        config=GraphConfig(enable_query_rewrite=True, query_rewrite_max_terms=10),
    )

    response = pipeline.run(SearchRequest(query="why does she get stuck?", top_k=2))

    assert response.rewritten_query == hyde_passage
    assert answerer.rewrite_calls == ["why does she get stuck?"]
    assert embedder.text_queries == [hyde_passage]
    assert answerer.calls[0]["query"] == "why does she get stuck?"


def test_query_rewrite_skips_visual_intent():
    from graph.models import GraphConfig

    embedder = FakeEmbedder()
    answerer = FakeAnswerer(rewrite="rewritten visual query")
    pipeline = QueryPipeline(
        embedder=embedder,
        transcript_index=FakeIndex([]),
        visual_index=FakeIndex([_visual_hit()]),
        answer_generator=answerer,
        config=GraphConfig(enable_query_rewrite=True),
    )

    response = pipeline.run(SearchRequest(query="Show me the speaker at a desk"))

    assert response.rewritten_query is None
    assert answerer.rewrite_calls == []
    assert embedder.visual_queries == ["Show me the speaker at a desk"]


def test_query_rewrite_skips_already_specific_queries():
    from graph.models import GraphConfig

    embedder = FakeEmbedder()
    answerer = FakeAnswerer(rewrite="rewritten query")
    pipeline = QueryPipeline(
        embedder=embedder,
        transcript_index=FakeIndex([_transcript_hit()]),
        visual_index=FakeIndex([]),
        answer_generator=answerer,
        config=GraphConfig(enable_query_rewrite=True, query_rewrite_max_terms=3),
    )

    query = "Where does she explain fear as the reason we stop chasing dreams?"
    response = pipeline.run(SearchRequest(query=query))

    assert response.rewritten_query is None
    assert answerer.rewrite_calls == []
    assert embedder.text_queries == [query]


def test_per_modality_gate_lets_transcript_pass_when_visual_below_threshold():
    """The transcript-and-visual indexes use different metrics (dotproduct vs
    cosine) so their score distributions differ. Per-modality thresholds let
    each modality have its own bar — a strong transcript hit alongside a
    weak visual hit must still answer (the legacy combined threshold could
    misclassify on near-ties)."""
    from graph.models import GraphConfig

    strong_transcript = _transcript_hit(score=0.45)
    weak_visual = _visual_hit(score=0.05)
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([strong_transcript]),
        visual_index=FakeIndex([weak_visual]),
        answer_generator=FakeAnswerer(),
        config=GraphConfig(
            min_transcript_source_score=0.2,
            min_visual_source_score=0.5,  # visual must clear a higher bar
        ),
    )

    response = pipeline.run(SearchRequest(query="self sabotage"))

    assert response.refused is False
    assert response.results


def test_per_modality_gate_refuses_when_both_below_threshold():
    """If neither modality clears its own threshold AND no lexical evidence is
    present, the gate must refuse — same UX as the legacy single-threshold gate."""
    from graph.models import GraphConfig

    weak_transcript = _transcript_hit(score=0.05)
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([weak_transcript]),
        visual_index=FakeIndex([]),
        answer_generator=FakeAnswerer(),
        config=GraphConfig(
            min_transcript_source_score=0.2,
            min_visual_source_score=0.2,
        ),
    )

    response = pipeline.run(SearchRequest(query="show me an unrelated thing entirely"))

    assert response.refused is True
    assert response.results == []


def test_bedrock_answer_failure_logs_and_falls_back_to_extractive(caplog):
    """When Bedrock raises, we degrade to an extractive answer — but log so the
    `bedrock_answer_error` metric filter can count real outages on the dashboard."""
    import logging

    class BrokenAnswerer:
        def generate(self, *, query: str, context: str, intent: str | None = None) -> str:
            raise RuntimeError("bedrock throttled")

    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit()]),
        visual_index=FakeIndex([]),
        answer_generator=BrokenAnswerer(),
    )

    with caplog.at_level(logging.ERROR, logger="video_rag.graph"):
        response = pipeline.run(SearchRequest(query="Where do they explain self sabotage?"))

    assert response.refused is False
    assert response.answer  # extractive fallback ran
    assert any("bedrock_answer_error" in record.message for record in caplog.records)


def test_confidence_scale_tracks_rrf_k_via_config():
    """Consumers who tune rrf_k can tune confidence_scale via config — no magic
    number hidden inline. Pipeline output should reflect their choice."""
    from graph.models import GraphConfig

    cfg = GraphConfig(rrf_k=30, confidence_scale=12.0)
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit()]),
        visual_index=FakeIndex([]),
        answer_generator=FakeAnswerer(),
        config=cfg,
    )
    response = pipeline.run(SearchRequest(query="Where do they explain self sabotage?"))
    # Top hit, rank 1, single list, rrf_k=30 → 1/31 ≈ 0.03226 × 12 → 0.387 (rounded).
    assert response.results
    assert response.results[0].score == 0.387
    assert response.confidence == 0.387


def test_llm_refusal_answer_propagates_as_refused():
    """When the LLM generates 'I could not find strong evidence', the pipeline
    must propagate refused=True rather than silently returning a bad answer."""

    class RefusingAnswerer:
        def generate(self, *, query: str, context: str, intent: str | None = None) -> str:
            return (
                "I could not find strong evidence for that in the indexed videos. "
                "The video focuses on different topics."
            )

        def rewrite_query(self, *, query: str) -> str:
            return query

    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit()]),
        visual_index=FakeIndex([]),
        answer_generator=RefusingAnswerer(),
    )

    response = pipeline.run(
        SearchRequest(query="Does the self-sabotage video explain salary negotiation?")
    )

    assert response.refused is True
    assert "could not find strong evidence" in response.answer.lower()
    assert response.confidence == 0.0
    assert response.results == []


def test_visual_intent_passes_intent_to_answer_generator():
    """Visual-intent queries pass intent='visual' to the answer generator so
    the prompt can include visual-evidence-aware guidance."""

    answerer = FakeAnswerer()
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit()]),
        visual_index=FakeIndex([_visual_hit()]),
        answer_generator=answerer,
        config=GraphConfig(enable_answer_generation=True),
    )

    pipeline.run(SearchRequest(query="Show me the speaker in the bedroom"))

    assert answerer.calls
    assert answerer.calls[0]["intent"] == "visual"


# ---------------------------------------------------------------------------
# Citation-order proof reranking tests
# ---------------------------------------------------------------------------


def _make_candidate(start: float, end: float, snippet: str = "") -> RetrievalCandidate:
    return RetrievalCandidate(
        id=f"vec-{int(start)}",
        rank=0,
        video_id="v1",
        title="Test Video",
        start_seconds=start,
        end_seconds=end,
        modality="transcript",
        score=0.5,
        snippet=snippet or f"Segment at {start}",
        thumbnail_url="https://example.com/thumb.jpg",
        seek_url=f"https://youtu.be/v1?t={int(start)}",
    )


def test_reorder_by_citations_promotes_cited_proofs():
    """Proofs matching cited timestamps should be moved to the front."""
    c1 = _make_candidate(0, 30)  # 0:00
    c2 = _make_candidate(120, 150)  # 2:00
    c3 = _make_candidate(377, 407)  # 6:17
    c4 = _make_candidate(540, 570)  # 9:00

    answer = (
        'Around 6:17, Altman states that Elon is "one of the great builders." '
        "At 2:00, he admires Elon's willingness."
    )

    result = _reorder_by_citations(answer, [c1, c2, c3, c4])
    assert result[0] is c3, "6:17 proof should be first (cited first)"
    assert result[1] is c2, "2:00 proof should be second (cited second)"
    assert result[2] is c1, "un-cited proofs keep original order"
    assert result[3] is c4


def test_reorder_by_citations_no_timestamps():
    """When the answer has no timestamps, order is unchanged."""
    c1 = _make_candidate(0, 30)
    c2 = _make_candidate(60, 90)
    answer = "The speaker discusses leadership extensively."
    result = _reorder_by_citations(answer, [c1, c2])
    assert result == [c1, c2]


def test_reorder_by_citations_empty_answer():
    """Empty answer leaves order unchanged."""
    c1 = _make_candidate(0, 30)
    assert _reorder_by_citations("", [c1]) == [c1]
    assert _reorder_by_citations("some answer", []) == []


def test_reorder_by_citations_tolerates_near_timestamps():
    """Citation at 6:17 (377s) should match a chunk starting at 370s."""
    c1 = _make_candidate(0, 30)
    c2 = _make_candidate(370, 400)  # close to 6:17 = 377s
    answer = "At 6:17, the speaker says..."
    result = _reorder_by_citations(answer, [c1, c2])
    assert result[0] is c2


def test_reorder_by_citations_deduplicates_same_timestamp():
    """Same timestamp cited twice doesn't double-pull the same candidate."""
    c1 = _make_candidate(377, 407)
    c2 = _make_candidate(0, 30)
    answer = "At 6:17 he says X. Later, revisiting 6:17, he adds Y."
    result = _reorder_by_citations(answer, [c1, c2])
    assert len(result) == 2
    assert result[0] is c1
