"""Public query cache and rate-limit controls.

These controls are optional. Local dev and tests keep the Phase 1-5 behavior
unless the DynamoDB table names are configured.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import boto3
from fastapi import HTTPException, Request, status
from shared import settings
from shared.schemas import SearchRequest, SearchResponse


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def cache_key_for(req: SearchRequest) -> str:
    payload = {
        "query": " ".join(req.query.lower().split()),
        "video_ids": ",".join(sorted(req.video_ids)) if req.video_ids else "",
        "top_k": req.top_k,
        "search_config": _search_config_fingerprint(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _search_config_fingerprint() -> dict[str, Any]:
    return {
        "version": settings.search_config_version,
        "hybrid": settings.enable_hybrid_transcript,
        "rerank": settings.enable_cross_encoder_rerank,
        "rewrite": settings.enable_query_rewrite,
        "hybrid_alpha": settings.hybrid_alpha,
    }


@dataclass
class QueryControls:
    cache_table: Any | None = None
    rate_table: Any | None = None
    now: Callable[[], float] = time.time

    def enforce_rate_limit(self, request: Request) -> None:
        if not self.rate_table:
            return

        now = int(self.now())
        window = max(settings.rate_limit_window_seconds, 1)
        limit = max(settings.rate_limit_max_requests, 1)
        window_id = now // window
        window_key = f"{_client_key(request)}:{window_id}"
        expires_at = now + (window * 2)
        response = self.rate_table.update_item(
            Key={"window_key": window_key},
            UpdateExpression="ADD #count :one SET expires_at = :expires_at",
            ExpressionAttributeNames={"#count": "count"},
            ExpressionAttributeValues={":one": 1, ":expires_at": expires_at},
            ReturnValues="UPDATED_NEW",
        )
        count = int(response.get("Attributes", {}).get("count", 1))
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Public search rate limit exceeded. Please try again shortly.",
            )

    def get_cached_response(self, req: SearchRequest) -> SearchResponse | None:
        if not self.cache_table:
            return None

        response = self.cache_table.get_item(Key={"cache_key": cache_key_for(req)})
        item = response.get("Item")
        if not item:
            return None
        expires_at = int(item.get("expires_at", 0))
        if expires_at <= int(self.now()):
            return None
        return SearchResponse.model_validate_json(item["response_json"])

    def put_cached_response(self, req: SearchRequest, response: SearchResponse) -> None:
        if not self.cache_table:
            return

        ttl = max(settings.query_cache_ttl_seconds, 1)
        self.cache_table.put_item(
            Item={
                "cache_key": cache_key_for(req),
                "expires_at": int(self.now()) + ttl,
                "response_json": response.model_dump_json(),
            }
        )


def query_controls_from_settings() -> QueryControls:
    if not (settings.dynamodb_query_cache_table or settings.dynamodb_rate_limit_table):
        return QueryControls()

    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    cache_table = (
        dynamodb.Table(settings.dynamodb_query_cache_table)
        if settings.dynamodb_query_cache_table
        else None
    )
    rate_table = (
        dynamodb.Table(settings.dynamodb_rate_limit_table)
        if settings.dynamodb_rate_limit_table
        else None
    )
    return QueryControls(cache_table=cache_table, rate_table=rate_table)
