"""Worker pipeline tests with fake AWS/media dependencies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ingest.media import FrameFile
from ingest.pipeline import IngestionWorker
from shared.schemas import (
    IndexingSummary,
    IngestJobMessage,
    TranscriptArtifact,
    TranscriptSegment,
    VideoMetadataArtifact,
)


class FakeTable:
    def __init__(self, *, existing_items: dict[str, dict[str, Any]] | None = None) -> None:
        self.updates: list[dict[str, Any]] = []
        self.puts: list[dict[str, Any]] = []
        self.gets: list[dict[str, Any]] = []
        self._items: dict[str, dict[str, Any]] = existing_items or {}

    def update_item(self, **kwargs) -> None:
        self.updates.append(kwargs)

    def put_item(self, **kwargs) -> None:
        self.puts.append(kwargs["Item"])

    def get_item(self, **kwargs) -> dict[str, Any]:
        self.gets.append(kwargs)
        key = kwargs.get("Key", {})
        if not key:
            return {}
        pk_value = next(iter(key.values()))
        item = self._items.get(pk_value)
        return {"Item": item} if item else {}


class FakeS3:
    def __init__(self) -> None:
        self.files: list[dict[str, Any]] = []
        self.objects: dict[str, str] = {}

    def upload_file(self, filename: str, bucket: str, key: str, ExtraArgs: dict[str, str]) -> None:
        assert Path(filename).exists()
        self.files.append({"bucket": bucket, "key": key, "extra": ExtraArgs})

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        assert Bucket == "test-bucket"
        assert ContentType == "application/json"
        self.objects[Key] = Body.decode("utf-8")


class FakeMedia:
    def __init__(self, *, fail_download: bool = False) -> None:
        self.fail_download = fail_download

    def fetch_metadata(self, youtube_url: str) -> VideoMetadataArtifact:
        return VideoMetadataArtifact(
            video_id="QkdBXUikRQc",
            youtube_url=youtube_url,
            title="Tiny Test Talk",
            author="Test Speaker",
            duration_seconds=90,
            thumbnail_url="https://example.com/thumb.jpg",
        )

    def download_video(self, youtube_url: str, work_dir: Path) -> Path:
        if self.fail_download:
            raise RuntimeError("download exploded")
        source = work_dir / "source.mp4"
        source.write_bytes(b"video")
        return source

    def extract_audio(self, source_path: Path, work_dir: Path) -> Path:
        audio = work_dir / "audio.m4a"
        audio.write_bytes(b"audio")
        return audio

    def extract_frames(self, source_path: Path, work_dir: Path) -> list[FrameFile]:
        one = work_dir / "frame_000001.jpg"
        two = work_dir / "frame_000002.jpg"
        one.write_bytes(b"one")
        two.write_bytes(b"two")
        return [FrameFile(one, 0), FrameFile(two, 30)]

    def transcribe_audio(self, audio_path: Path, video_id: str) -> TranscriptArtifact:
        return TranscriptArtifact(
            video_id=video_id,
            language="en",
            segments=[TranscriptSegment(start_seconds=0, end_seconds=5, text="hello world")],
        )


class FakeIndexer:
    def __init__(self) -> None:
        self.calls = []

    def index_video(self, **kwargs) -> IndexingSummary:
        self.calls.append(kwargs)
        return IndexingSummary(
            video_id=kwargs["metadata"].video_id,
            transcript_vectors=1,
            visual_vectors=len(kwargs["frames"]),
        )


def _message() -> IngestJobMessage:
    return IngestJobMessage(
        job_id="yt_QkdBXUikRQc",
        video_id="QkdBXUikRQc",
        youtube_url="https://youtu.be/QkdBXUikRQc",
        requested_at="2026-06-02T12:00:00+00:00",
    )


def test_worker_process_writes_artifacts_and_completes_job():
    jobs = FakeTable()
    videos = FakeTable()
    s3 = FakeS3()
    indexer = FakeIndexer()
    worker = IngestionWorker(
        bucket="test-bucket",
        jobs_table=jobs,
        videos_table=videos,
        s3_client=s3,
        media=FakeMedia(),
        indexer=indexer,
    )

    worker.process(_message())

    statuses = [update["ExpressionAttributeValues"][":status"] for update in jobs.updates]
    assert statuses == ["downloading", "downloading", "transcribing", "embedding", "completed"]
    assert indexer.calls[0]["metadata"].title == "Tiny Test Talk"
    assert indexer.calls[0]["transcript"].segments[0].text == "hello world"
    assert len(indexer.calls[0]["frames"]) == 2
    assert indexer.calls[0]["frame_keys"] == [
        "videos/QkdBXUikRQc/frames/frame_000001.jpg",
        "videos/QkdBXUikRQc/frames/frame_000002.jpg",
    ]
    assert videos.puts[0]["video_id"] == "QkdBXUikRQc"
    assert videos.puts[0]["status"] == "ingested"
    assert [file["key"] for file in s3.files] == [
        "videos/QkdBXUikRQc/audio/audio.m4a",
        "videos/QkdBXUikRQc/frames/frame_000001.jpg",
        "videos/QkdBXUikRQc/frames/frame_000002.jpg",
    ]
    assert set(s3.objects) == {
        "videos/QkdBXUikRQc/source/metadata.json",
        "videos/QkdBXUikRQc/frames/frames.json",
        "videos/QkdBXUikRQc/transcript/transcript.json",
        "videos/QkdBXUikRQc/vectors/indexing_summary.json",
    }


def test_worker_marks_failed_and_reraises_on_retryable_error():
    jobs = FakeTable()
    worker = IngestionWorker(
        bucket="test-bucket",
        jobs_table=jobs,
        videos_table=FakeTable(),
        s3_client=FakeS3(),
        media=FakeMedia(fail_download=True),
    )

    with pytest.raises(RuntimeError, match="download exploded"):
        worker.process(_message())

    failed = jobs.updates[-1]["ExpressionAttributeValues"]
    assert failed[":status"] == "failed"
    assert failed[":error"] == "download exploded"


def test_worker_skips_already_completed_job_on_redelivery():
    """SQS delivery is at-least-once. A redelivered completed job must not
    re-download, re-transcribe, or re-embed — costs money and time."""
    jobs = FakeTable(existing_items={"yt_QkdBXUikRQc": {"status": "completed"}})
    videos = FakeTable()
    s3 = FakeS3()
    indexer = FakeIndexer()
    media = FakeMedia()
    worker = IngestionWorker(
        bucket="test-bucket",
        jobs_table=jobs,
        videos_table=videos,
        s3_client=s3,
        media=media,
        indexer=indexer,
    )

    worker.process(_message())

    # Critical assertions: NO writes anywhere, only the lookup happened.
    assert jobs.gets, "must have probed job status before processing"
    assert jobs.updates == []
    assert videos.puts == []
    assert s3.files == []
    assert s3.objects == {}
    assert indexer.calls == []


def test_worker_proceeds_when_lookup_fails_transiently():
    """A transient DDB read failure must not block the worker from doing the
    work — better to redo an idempotent step than to drop a real job."""

    class FailingTable(FakeTable):
        def get_item(self, **kwargs) -> dict[str, Any]:
            raise RuntimeError("ddb hiccup")

    jobs = FailingTable()
    worker = IngestionWorker(
        bucket="test-bucket",
        jobs_table=jobs,
        videos_table=FakeTable(),
        s3_client=FakeS3(),
        media=FakeMedia(),
        indexer=FakeIndexer(),
    )

    # Should NOT raise: the lookup failure is swallowed and the pipeline proceeds.
    worker.process(_message())
    assert jobs.updates, "pipeline should have run through to update statuses"
