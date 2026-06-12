"""FastAPI application entrypoint.

Run locally with `uvicorn api.main:app --reload`. In production this is
deployed behind API Gateway via Mangum (added in the deployment phase).
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from shared import settings

from .routes_admin import router as admin_router
from .routes_public import router as public_router

app = FastAPI(title="Multimodal Video RAG API", version="0.1.0")
logger = logging.getLogger("video_rag.api")
logger.setLevel(logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "api_request request_id=%s method=%s path=%s status_code=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["x-request-id"] = request_id
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(public_router)
app.include_router(admin_router)


_mangum = Mangum(app)


def _flush_langsmith_traces() -> None:
    """Drain pending LangSmith uploads before Lambda freezes.

    The LangSmith SDK posts runs from a background thread in batches. Lambda
    freezes the execution environment the moment the handler returns, so
    without a synchronous flush the tail of every trace — the final node's
    end event (its outputs/duration) and the root run completion — is lost
    and traces appear stuck pending. Local processes don't hit this because
    Python's exit hooks drain the queue.
    """
    if not (settings.langsmith_tracing and settings.langsmith_api_key):
        return
    try:
        from langchain_core.tracers.langchain import get_client, wait_for_all_tracers

        wait_for_all_tracers()
        get_client().flush()
    except Exception:
        logger.exception("langsmith_flush_error")


def handler(event, context):
    try:
        return _mangum(event, context)
    finally:
        _flush_langsmith_traces()
