"""Public, read-only endpoints: the demo library and search over it."""

from __future__ import annotations

from fastapi import APIRouter
from shared.schemas import DemoVideo, SearchRequest, SearchResponse

from .mock_data import DEMO_VIDEOS, mock_search

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/videos", response_model=list[DemoVideo])
def list_videos() -> list[DemoVideo]:
    return DEMO_VIDEOS


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    return mock_search(req)
