"""Helpers shared by the API and worker for Phase 2 ingestion.

These functions keep idempotency and artifact paths deterministic so the API,
worker, tests, and later embedding stages all agree on the same identifiers.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel

YOUTUBE_ID_RE = re.compile(r"(?:youtu\.be/|v=|/embed/|/shorts/)([A-Za-z0-9_-]{11})")


class NormalizedYouTubeUrl(BaseModel):
    video_id: str
    youtube_url: str


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize_youtube_url(url: str) -> NormalizedYouTubeUrl:
    """Extract the YouTube video id and return the canonical watch URL."""
    match = YOUTUBE_ID_RE.search(url.strip())
    if not match:
        raise ValueError("Expected a YouTube URL with an 11-character video id")
    video_id = match.group(1)
    return NormalizedYouTubeUrl(video_id=video_id, youtube_url=f"https://youtu.be/{video_id}")


def job_id_for_video(video_id: str) -> str:
    return f"yt_{video_id}"


def artifact_prefix(video_id: str) -> str:
    return f"videos/{video_id}"


def metadata_key(video_id: str) -> str:
    return f"{artifact_prefix(video_id)}/source/metadata.json"


def audio_key(video_id: str) -> str:
    return f"{artifact_prefix(video_id)}/audio/audio.m4a"


def transcript_key(video_id: str) -> str:
    return f"{artifact_prefix(video_id)}/transcript/transcript.json"


def frame_key(video_id: str, frame_number: int) -> str:
    return f"{artifact_prefix(video_id)}/frames/frame_{frame_number:06d}.jpg"


def bm25_stats_key(video_id: str) -> str:
    """S3 key for the per-video BM25 encoder state (used at query time for hybrid)."""
    return f"{artifact_prefix(video_id)}/vectors/bm25_stats.json"
