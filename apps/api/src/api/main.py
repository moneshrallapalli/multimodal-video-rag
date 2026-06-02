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
        "api_request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    response.headers["x-request-id"] = request_id
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(public_router)
app.include_router(admin_router)


handler = Mangum(app)
