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

    def query(self, vector, *, top_k, metadata_filter=None, namespace=None):
        self.calls.append(
            {
                "vector": vector,
                "top_k": top_k,
                "metadata_filter": metadata_filter,
                "namespace": namespace,
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
