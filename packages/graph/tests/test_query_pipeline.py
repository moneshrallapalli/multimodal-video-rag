"""Phase 4 query pipeline tests with fake service clients."""

from __future__ import annotations

from graph.pipeline import QueryPipeline
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
    def __init__(self, answer: str = "Grounded answer with a timestamp around 1:15.") -> None:
        self.answer = answer
        self.calls = []

    def generate(self, *, query: str, context: str) -> str:
        self.calls.append({"query": query, "context": context})
        return self.answer


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


def test_visual_query_routes_to_visual_index_only_with_video_filter():
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

    response = pipeline.run(
        SearchRequest(query="Show me the speaker at a desk", video_id="QkdBXUikRQc")
    )

    assert response.refused is False
    assert response.intent == "visual"
    assert response.answer == (
        "The strongest visual match is around 0:00 in “Stop Dreaming and Start Doing | "
        "Self-Sabotage”."
    )
    assert response.results[0].modality == "visual"
    assert visual.calls[0]["metadata_filter"] == {"video_id": {"$eq": "QkdBXUikRQc"}}
    assert transcript.calls == []
    assert answerer.calls == []


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
    answerer = FakeAnswerer()
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
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit(score=0.5)]),
        visual_index=FakeIndex([_visual_hit(score=0.4)]),
        answer_generator=FakeAnswerer(),
        config=GraphConfig(enable_cross_encoder_rerank=True),
        cross_encoder_reranker=fake_reranker,
    )

    response = pipeline.run(SearchRequest(query="self sabotage", top_k=2))

    assert len(fake_reranker.calls) == 1
    assert len(fake_reranker.calls[0]) == 2
    assert response.results[0].modality == "visual"
    assert response.results[0].rank == 1
    assert response.results[1].modality == "transcript"


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
        def generate(self, *, query: str, context: str) -> str:
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
