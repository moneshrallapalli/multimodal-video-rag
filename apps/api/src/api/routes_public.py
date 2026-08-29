"""Public, read-only endpoints: the demo library and search over it."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from shared.schemas import DemoVideo, PipelineEvent, SearchRequest, SearchResponse

from .query_controls import query_controls_from_settings
from .search_service import search_videos, search_videos_stream
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


@router.post("/search/stream")
def search_stream(req: SearchRequest, request: Request) -> StreamingResponse:
    """SSE log of the same QueryPipeline run as POST /api/search.

    Events are real node start/finish records. The final event is SearchResponse.
    Cache is not used as a shortcut so the UI can watch the live path.
    """
    controls = query_controls_from_settings()
    controls.enforce_rate_limit(request)

    def frames() -> Iterator[str]:
        final: SearchResponse | None = None
        for item in search_videos_stream(req):
            if isinstance(item, PipelineEvent):
                yield f"event: node\ndata: {item.model_dump_json()}\n\n"
            elif isinstance(item, SearchResponse):
                final = item
                yield f"event: final\ndata: {item.model_dump_json()}\n\n"
        if final is not None:
            controls.put_cached_response(req, final)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
