"""FastAPI application entrypoint.

Run locally with `uvicorn api.main:app --reload`. In production this is
deployed behind API Gateway via Mangum (added in the deployment phase).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared import settings

from .routes_admin import router as admin_router
from .routes_public import router as public_router

app = FastAPI(title="Multimodal Video RAG API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(public_router)
app.include_router(admin_router)


# Lambda handler (API Gateway) — enable in the deployment phase:
# from mangum import Mangum
# handler = Mangum(app)
