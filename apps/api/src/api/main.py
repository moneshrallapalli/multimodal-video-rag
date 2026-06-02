"""FastAPI application entrypoint.

Run locally with `uvicorn api.main:app --reload`. In production this is
deployed behind API Gateway via Mangum (added in the deployment phase).
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Multimodal Video RAG API", version="0.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Lambda handler (API Gateway) — enable in the deployment phase:
# from mangum import Mangum
# handler = Mangum(app)
