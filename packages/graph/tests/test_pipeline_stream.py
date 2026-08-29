"""Live node events from QueryPipeline.run_stream()."""

from __future__ import annotations

from graph.models import GraphConfig
from graph.pipeline import QueryPipeline
from shared.schemas import PipelineEvent, SearchRequest, SearchResponse
from test_query_pipeline import (
    FakeAnswerer,
    FakeCrossEncoderReranker,
    FakeEmbedder,
    FakeIndex,
    SequencedIndex,
    _transcript_hit,
    _visual_hit,
)


def _completions(items: list[PipelineEvent | SearchResponse]) -> list[PipelineEvent]:
    return [item for item in items if isinstance(item, PipelineEvent) and item.status != "started"]


def test_run_stream_happy_path_matches_run_and_skips_rewrite():
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit()]),
        visual_index=FakeIndex([_visual_hit()]),
        answer_generator=FakeAnswerer(),
    )
    request = SearchRequest(query="Where do they explain self sabotage?")
    expected = pipeline.run(request)

    items = list(pipeline.run_stream(request))
    assert isinstance(items[-1], SearchResponse)
    final = items[-1]
    assert final.answer == expected.answer
    assert final.refused is False
    assert final.intent == expected.intent
    assert [result.start_seconds for result in final.results] == [
        result.start_seconds for result in expected.results
    ]

    completions = _completions(items)
    assert (completions[0].node, completions[0].status) == ("validate_query", "ok")
    assert (completions[1].node, completions[1].status) == ("classify_intent", "ok")
    assert completions[1].payload["intent"] == "transcript"
    retrieve = {(item.node, item.status) for item in completions[2:4]}
    assert retrieve == {("retrieve_transcript", "ok"), ("retrieve_visual", "ok")}
    transcript = next(item for item in completions if item.node == "retrieve_transcript")
    assert transcript.payload["hit_count"] == 1
    assert transcript.payload["hits"][0]["video_id"] == "QkdBXUikRQc"
    assert completions[4].node == "fuse_results"
    assert completions[4].payload["reranked"] is False
    assert (completions[5].node, completions[5].status) == ("apply_retrieval_gate", "ok")
    assert completions[5].payload["passed"] is True
    assert (completions[6].node, completions[6].status) == ("rewrite_query", "skipped")
    assert (completions[7].node, completions[7].status) == ("build_context", "ok")
    assert (completions[8].node, completions[8].status) == ("generate_answer", "ok")
    assert completions[8].payload["refused"] is False
    assert completions[8].payload["answer_preview"]


def test_run_stream_gate_refusal_is_visible():
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([]),
        visual_index=FakeIndex([]),
        answer_generator=FakeAnswerer(),
    )

    items = list(pipeline.run_stream(SearchRequest(query="what is today's weather")))
    final = items[-1]
    assert isinstance(final, SearchResponse)
    assert final.refused is True
    assert final.refusal_reason == "retrieval_gate"

    completions = _completions(items)
    gate = next(item for item in completions if item.node == "apply_retrieval_gate")
    assert gate.status == "refused"
    assert gate.payload["passed"] is False
    assert gate.payload["reason"] == "retrieval_gate"
    rewrite = next(item for item in completions if item.node == "rewrite_query")
    assert rewrite.status == "skipped"
    generate = next(item for item in completions if item.node == "generate_answer")
    assert generate.status == "skipped"


def test_run_stream_rewrite_retry_emits_rewrite_and_retrieve_retry():
    hyde = "self sabotage fear of failure planning"
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=SequencedIndex([[], [_transcript_hit()]]),
        visual_index=FakeIndex([]),
        answer_generator=FakeAnswerer(rewrite=hyde),
        config=GraphConfig(enable_query_rewrite=True),
    )

    items = list(pipeline.run_stream(SearchRequest(query="why stuck?", top_k=2)))
    final = items[-1]
    assert isinstance(final, SearchResponse)
    assert final.refused is False
    assert final.rewritten_query == hyde

    completions = _completions(items)
    gates = [item for item in completions if item.node == "apply_retrieval_gate"]
    assert [item.status for item in gates] == ["refused", "ok"]
    rewrite = [item for item in completions if item.node == "rewrite_query"]
    assert len(rewrite) == 1
    assert rewrite[0].status == "ok"
    assert rewrite[0].payload["rewritten_query"] == hyde
    transcript = [item for item in completions if item.node == "retrieve_transcript"]
    assert [item.status for item in transcript] == ["ok", "retry"]
    assert transcript[1].payload["hit_count"] == 1


def test_run_stream_cross_encoder_payload_matches_eligibility():
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        transcript_index=FakeIndex([_transcript_hit()]),
        visual_index=FakeIndex([_visual_hit()]),
        answer_generator=FakeAnswerer(),
        config=GraphConfig(enable_cross_encoder_rerank=True),
        cross_encoder_reranker=FakeCrossEncoderReranker(scores=[0.2, 0.8]),
    )

    items = list(pipeline.run_stream(SearchRequest(query="self sabotage", top_k=2)))
    fuse = next(item for item in _completions(items) if item.node == "fuse_results")
    assert fuse.payload["reranked"] is True
    assert fuse.payload["fused_count"] == 2
