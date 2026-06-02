"""Admin endpoints: shared-secret login + ingestion and job tracking."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from shared.schemas import (
    IngestRequest,
    IngestResponse,
    JobsResponse,
    LoginRequest,
    SessionStatus,
)

from . import auth
from .ingestion_store import enqueue_ingestion, list_jobs

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login", response_model=SessionStatus)
def login(body: LoginRequest, response: Response) -> SessionStatus:
    if not auth.verify_password(body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    auth.issue_session(response)
    return SessionStatus(authenticated=True)


@router.post("/logout", response_model=SessionStatus)
def logout(response: Response) -> SessionStatus:
    auth.clear_session(response)
    return SessionStatus(authenticated=False)


@router.get("/session", response_model=SessionStatus)
def session(request: Request) -> SessionStatus:
    return SessionStatus(authenticated=auth.is_authenticated(request))


@router.get("/jobs", response_model=JobsResponse, dependencies=[Depends(auth.require_admin)])
def jobs() -> JobsResponse:
    return list_jobs()


@router.post("/ingest", response_model=IngestResponse, dependencies=[Depends(auth.require_admin)])
def ingest(body: IngestRequest) -> IngestResponse:
    try:
        return enqueue_ingestion(body.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
