"""Public, read-only endpoints: the demo library and search over it."""

from __future__ import annotations

from fastapi import APIRouter, Request
from shared.schemas import DemoVideo, SearchRequest, SearchResponse

from .query_controls import query_controls_from_settings
from .search_service import search_videos
from .video_catalog import list_public_videos

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/videos", response_model=list[DemoVideo])
def list_videos() -> list[DemoVideo]:
    return list_public_videos()


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, request: Request) -> SearchResponse:
    controls = query_controls_from_settings()
    controls.enforce_rate_limit(request)
    cached = controls.get_cached_response(req)
    if cached:
        return cached
    response = search_videos(req)
    controls.put_cached_response(req, response)
    return response
