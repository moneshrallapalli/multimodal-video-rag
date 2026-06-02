"""Internal models for the Phase 4 query graph."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CandidateModality = Literal["visual", "transcript"]


class RetrievalCandidate(BaseModel):
    id: str
    video_id: str
    title: str
    modality: CandidateModality
    start_seconds: float
    end_seconds: float
    score: float
    snippet: str
    thumbnail_url: str
    seek_url: str
    s3_uri: str | None = None
    rank: int = 0


class GraphConfig(BaseModel):
    retrieve_top_k: int = 8
    rrf_k: int = 60
    min_source_score: float = 0.2
    no_answer_message: str = (
        "I could not find strong evidence for that in the indexed videos. "
        "Try a more specific visual description or search within a single video."
    )


def thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def seek_url(video_id: str, seconds: float) -> str:
    return f"https://youtu.be/{video_id}?t={int(seconds)}"
