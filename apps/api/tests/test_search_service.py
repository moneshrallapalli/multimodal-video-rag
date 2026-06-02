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


def test_search_service_returns_safe_refusal_on_graph_error(monkeypatch):
    class BrokenPipeline:
        def run(self, req: SearchRequest) -> SearchResponse:
            raise RuntimeError("pinecone down")

    monkeypatch.setattr(settings, "pinecone_api_key", "key")
    monkeypatch.setattr(search_service, "_pipeline", lambda: BrokenPipeline())

    response = search_service.search_videos(SearchRequest(query="self sabotage"))

    assert response.refused is True
    assert response.intent == "no_answer"
    assert response.results == []
