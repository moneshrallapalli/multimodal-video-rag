"""Typed request/response contracts shared by the API and mirrored in the web app.

These models are the single source of truth for the Phase 1 mocked endpoints. Later
phases replace the mock implementations behind these exact shapes, so the frontend does
not change when real ingestion, retrieval, and generation land.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Modality = Literal["visual", "transcript"]
QueryIntent = Literal["visual", "transcript", "hybrid", "timestamp", "summary", "no_answer"]
JobStatus = Literal["queued", "downloading", "transcribing", "embedding", "completed", "failed"]


# ── Public: demo library + search ─────────────────────────────────────


class DemoVideo(BaseModel):
    """A video in the read-only public demo library."""

    id: str  # YouTube video id
    title: str
    author: str
    thumbnail_url: str
    youtube_url: str
    duration_seconds: int | None = None
    indexed: bool = True


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    video_id: str | None = None  # optional single-video filter
    top_k: int = Field(default=8, ge=1, le=20)


class SearchResult(BaseModel):
    """One rich result card: a timestamped, cited moment in a video."""

    rank: int
    video_id: str
    title: str
    start_seconds: float
    end_seconds: float
    modality: Modality
    score: float = Field(ge=0.0, le=1.0)
    snippet: str
    thumbnail_url: str
    seek_url: str  # e.g. https://youtu.be/<id>?t=<start_seconds>


class SearchResponse(BaseModel):
    query: str
    rewritten_query: str | None = None
    intent: QueryIntent
    answer: str | None = None
    refused: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    results: list[SearchResult] = Field(default_factory=list)


# ── Admin: auth + ingestion ───────────────────────────────────────────


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


class SessionStatus(BaseModel):
    authenticated: bool


class IngestRequest(BaseModel):
    youtube_url: str = Field(min_length=1)


class Job(BaseModel):
    """An ingestion job tracked in the admin console."""

    id: str
    youtube_url: str
    video_id: str | None = None
    title: str | None = None
    status: JobStatus
    progress: int = Field(default=0, ge=0, le=100)
    created_at: str
    updated_at: str
    error: str | None = None


class IngestResponse(BaseModel):
    job: Job


class JobsResponse(BaseModel):
    jobs: list[Job]


# ── Ingestion pipeline internals ─────────────────────────────────────


class IngestJobMessage(BaseModel):
    """SQS payload consumed by the Phase 2 worker."""

    job_id: str
    video_id: str
    youtube_url: str
    requested_at: str


class VideoMetadataArtifact(BaseModel):
    """Normalized YouTube metadata stored in S3."""

    video_id: str
    youtube_url: str
    title: str | None = None
    author: str | None = None
    duration_seconds: int | None = None
    thumbnail_url: str | None = None


class FrameArtifact(BaseModel):
    """One extracted frame artifact."""

    frame_id: str
    video_id: str
    timestamp_seconds: float
    s3_key: str


class TranscriptSegment(BaseModel):
    """A timestamp-aligned transcript segment."""

    start_seconds: float
    end_seconds: float
    text: str


class TranscriptArtifact(BaseModel):
    """Transcript artifact written by the worker."""

    video_id: str
    language: str | None = None
    segments: list[TranscriptSegment] = Field(default_factory=list)


class TranscriptChunk(BaseModel):
    """A sentence/segment-aware transcript chunk ready for embedding."""

    chunk_id: str
    video_id: str
    start_seconds: float
    end_seconds: float
    text: str


class SparseVector(BaseModel):
    """Sparse vector format Pinecone expects: parallel index/value lists."""

    indices: list[int] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)


class VectorRecord(BaseModel):
    """A dense vector plus Pinecone metadata; optional sparse for hybrid search."""

    id: str
    values: list[float]
    metadata: dict[str, str | int | float | bool]
    sparse_values: SparseVector | None = None


class IndexingSummary(BaseModel):
    """Counts from a Phase 3 indexing pass.

    `bm25_stats` carries the fitted BM25 encoder state when hybrid sparse
    indexing was performed; clients persist it to S3 for query-time hybrid use.
    """

    video_id: str
    transcript_vectors: int = 0
    visual_vectors: int = 0
    bm25_stats: dict[str, Any] | None = None


class RetrievalHit(BaseModel):
    """A timestamped hit returned by a Pinecone smoke query."""

    id: str
    score: float
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)
