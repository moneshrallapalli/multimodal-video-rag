"""Unit tests for optional public query cache and rate-limit controls."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from api.query_controls import QueryControls, cache_key_for
from fastapi import HTTPException
from shared import settings
from shared.schemas import SearchRequest, SearchResponse


class FakeCacheTable:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def get_item(self, *, Key: dict[str, str]) -> dict[str, Any]:
        item = self.items.get(Key["cache_key"])
        return {"Item": item} if item else {}

    def put_item(self, *, Item: dict[str, Any]) -> None:
        self.items[Item["cache_key"]] = dict(Item)


class FakeRateTable:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def update_item(
        self,
        *,
        Key: dict[str, str],
        UpdateExpression: str,
        ExpressionAttributeNames: dict[str, str],
        ExpressionAttributeValues: dict[str, int],
        ReturnValues: str,
    ) -> dict[str, Any]:
        assert UpdateExpression.startswith("ADD")
        assert ExpressionAttributeNames == {"#count": "count"}
        assert ReturnValues == "UPDATED_NEW"
        key = Key["window_key"]
        self.counts[key] = self.counts.get(key, 0) + ExpressionAttributeValues[":one"]
        return {"Attributes": {"count": self.counts[key]}}


def _request(ip: str = "203.0.113.1"):
    return SimpleNamespace(headers={}, client=SimpleNamespace(host=ip))


def test_cache_key_normalizes_query_whitespace_and_case():
    first = SearchRequest(query="  Self   Sabotage  ", top_k=8)
    second = SearchRequest(query="self sabotage", top_k=8)

    assert cache_key_for(first) == cache_key_for(second)


def test_cache_key_changes_with_search_config(monkeypatch):
    req = SearchRequest(query="self sabotage", top_k=8)
    monkeypatch.setattr(settings, "search_config_version", "dense-v1")
    dense_key = cache_key_for(req)

    monkeypatch.setattr(settings, "search_config_version", "hybrid-rerank-rewrite-v1")

    assert cache_key_for(req) != dense_key


def test_cache_round_trip(monkeypatch):
    monkeypatch.setattr(settings, "query_cache_ttl_seconds", 60)
    cache_table = FakeCacheTable()
    controls = QueryControls(cache_table=cache_table, now=lambda: 1000)
    req = SearchRequest(query="self sabotage")
    response = SearchResponse(
        query=req.query,
        intent="transcript",
        answer="cached answer",
        confidence=0.9,
        results=[],
    )

    controls.put_cached_response(req, response)

    assert controls.get_cached_response(req) == response


def test_expired_cache_entry_is_ignored():
    cache_table = FakeCacheTable()
    req = SearchRequest(query="self sabotage")
    cache_table.items[cache_key_for(req)] = {
        "expires_at": 999,
        "response_json": SearchResponse(
            query=req.query,
            intent="transcript",
            confidence=0.9,
            results=[],
        ).model_dump_json(),
    }
    controls = QueryControls(cache_table=cache_table, now=lambda: 1000)

    assert controls.get_cached_response(req) is None


def test_rate_limit_rejects_after_configured_limit(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
    monkeypatch.setattr(settings, "rate_limit_max_requests", 2)
    controls = QueryControls(rate_table=FakeRateTable(), now=lambda: 120)

    controls.enforce_rate_limit(_request())
    controls.enforce_rate_limit(_request())
    with pytest.raises(HTTPException) as exc:
        controls.enforce_rate_limit(_request())

    assert exc.value.status_code == 429
