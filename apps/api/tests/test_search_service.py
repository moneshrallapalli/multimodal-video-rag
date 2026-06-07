"""Search service wiring tests."""

from __future__ import annotations

from api import search_service
from shared import settings
from shared.schemas import SearchRequest, SearchResponse


class FakePipeline:
    def __init__(self) -> None:
        self.requests = []

    def run(self, req: SearchRequest) -> SearchResponse:
        self.requests.append(req)
        return SearchResponse(
            query=req.query,
            intent="transcript",
            answer="real graph answer",
            confidence=0.8,
            results=[],
        )


def test_search_service_uses_mock_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "pinecone_api_key", "")

    response = search_service.search_videos(SearchRequest(query="what is today's weather"))

    assert response.refused is True
    assert response.intent == "no_answer"


def test_search_service_uses_graph_when_configured(monkeypatch):
    fake = FakePipeline()
    monkeypatch.setattr(settings, "pinecone_api_key", "key")
    monkeypatch.setattr(search_service, "_pipeline", lambda: fake)

    response = search_service.search_videos(SearchRequest(query="self sabotage"))

    assert response.answer == "real graph answer"
    assert fake.requests[0].query == "self sabotage"


def test_search_service_returns_safe_refusal_on_graph_error(monkeypatch, caplog):
    class BrokenPipeline:
        def run(self, req: SearchRequest) -> SearchResponse:
            raise RuntimeError("pinecone down")

    monkeypatch.setattr(settings, "pinecone_api_key", "key")
    monkeypatch.setattr(search_service, "_pipeline", lambda: BrokenPipeline())

    import logging

    with caplog.at_level(logging.ERROR, logger="video_rag.api.search"):
        response = search_service.search_videos(SearchRequest(query="self sabotage"))

    assert response.refused is True
    assert response.intent == "no_answer"
    assert response.results == []
    # Critical: the failure must emit `search_pipeline_error` so the CloudWatch
    # metric filter can distinguish API failures from legitimate refusals.
    assert any("search_pipeline_error" in record.message for record in caplog.records)


def test_pipeline_uses_runtime_graph_feature_flags(monkeypatch):
    captured = {}
    fake_reranker = object()

    class CapturingPipeline:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(settings, "enable_hybrid_transcript", True)
    monkeypatch.setattr(settings, "enable_cross_encoder_rerank", True)
    monkeypatch.setattr(settings, "enable_query_rewrite", True)
    monkeypatch.setattr(settings, "hybrid_alpha", 0.42)
    monkeypatch.setattr(settings, "cross_encoder_reranker_function_name", "reranker-live")
    monkeypatch.setattr(search_service, "QueryPipeline", CapturingPipeline)
    monkeypatch.setattr(search_service, "_cross_encoder_reranker", lambda: fake_reranker)
    search_service._pipeline.cache_clear()

    try:
        search_service._pipeline()
    finally:
        search_service._pipeline.cache_clear()

    config = captured["config"]
    assert config.enable_hybrid_transcript is True
    assert config.enable_cross_encoder_rerank is True
    assert config.enable_query_rewrite is True
    assert config.hybrid_alpha == 0.42
    assert captured["transcript_bm25_resolver"] is search_service._bm25_encoder
    assert captured["cross_encoder_reranker"] is fake_reranker


def test_pipeline_uses_local_reranker_when_no_function_name(monkeypatch):
    """When cross-encoder reranking is enabled but no remote Lambda function name
    is configured, the pipeline should use a LocalCrossEncoderReranker (model
    baked into the container image) rather than disabling reranking entirely."""
    from unittest.mock import MagicMock

    from api.reranking import LocalCrossEncoderReranker

    captured = {}

    class CapturingPipeline:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    # Mock CrossEncoder so CI doesn't download from HuggingFace
    monkeypatch.setattr("sentence_transformers.CrossEncoder", MagicMock)

    monkeypatch.setattr(settings, "enable_cross_encoder_rerank", True)
    monkeypatch.setattr(settings, "cross_encoder_reranker_function_name", "")
    monkeypatch.setattr(search_service, "QueryPipeline", CapturingPipeline)
    search_service._pipeline.cache_clear()
    search_service._cross_encoder_reranker.cache_clear()

    try:
        search_service._pipeline()
    finally:
        search_service._pipeline.cache_clear()
        search_service._cross_encoder_reranker.cache_clear()

    assert captured["config"].enable_cross_encoder_rerank is True
    assert isinstance(captured["cross_encoder_reranker"], LocalCrossEncoderReranker)


def test_bm25_encoder_loads_from_s3_by_video_id(monkeypatch):
    calls: list[tuple[str, str]] = []
    fake_encoder = object()

    def fake_load_from_s3(*, bucket: str, video_id: str):
        calls.append((bucket, video_id))
        return fake_encoder

    monkeypatch.setattr(settings, "s3_bucket", "artifact-bucket")
    monkeypatch.setattr(search_service.BM25Encoder, "load_from_s3", staticmethod(fake_load_from_s3))
    search_service._bm25_encoder.cache_clear()

    try:
        assert search_service._bm25_encoder("video-a") is fake_encoder
        assert search_service._bm25_encoder("video-a") is fake_encoder
    finally:
        search_service._bm25_encoder.cache_clear()

    assert calls == [("artifact-bucket", "video-a")]


def test_bm25_encoder_loads_corpus_stats_for_unfiltered_search(monkeypatch):
    calls: list[str] = []
    fake_encoder = object()

    def fake_load_corpus_from_s3(*, bucket: str):
        calls.append(bucket)
        return fake_encoder

    monkeypatch.setattr(settings, "s3_bucket", "artifact-bucket")
    monkeypatch.setattr(
        search_service.BM25Encoder,
        "load_corpus_from_s3",
        staticmethod(fake_load_corpus_from_s3),
    )
    search_service._bm25_encoder.cache_clear()

    try:
        assert search_service._bm25_encoder(None) is fake_encoder
        assert search_service._bm25_encoder(None) is fake_encoder
    finally:
        search_service._bm25_encoder.cache_clear()

    assert calls == ["artifact-bucket"]
