"""Shared ingestion helper coverage."""

from __future__ import annotations

import pytest
from shared.ingestion import (
    audio_key,
    frame_key,
    job_id_for_video,
    metadata_key,
    normalize_youtube_url,
    transcript_key,
)


def test_normalize_youtube_url_accepts_common_forms():
    for url in (
        "https://youtu.be/QkdBXUikRQc",
        "https://www.youtube.com/watch?v=QkdBXUikRQc&t=30s",
        "https://www.youtube.com/embed/QkdBXUikRQc",
        "https://www.youtube.com/shorts/QkdBXUikRQc",
    ):
        normalized = normalize_youtube_url(url)
        assert normalized.video_id == "QkdBXUikRQc"
        assert normalized.youtube_url == "https://youtu.be/QkdBXUikRQc"


def test_normalize_youtube_url_rejects_invalid_url():
    with pytest.raises(ValueError, match="YouTube URL"):
        normalize_youtube_url("https://example.com/not-a-video")


def test_ingestion_ids_and_artifact_keys_are_deterministic():
    assert job_id_for_video("QkdBXUikRQc") == "yt_QkdBXUikRQc"
    assert metadata_key("QkdBXUikRQc") == "videos/QkdBXUikRQc/source/metadata.json"
    assert audio_key("QkdBXUikRQc") == "videos/QkdBXUikRQc/audio/audio.m4a"
    assert transcript_key("QkdBXUikRQc") == "videos/QkdBXUikRQc/transcript/transcript.json"
    assert frame_key("QkdBXUikRQc", 7) == "videos/QkdBXUikRQc/frames/frame_000007.jpg"
