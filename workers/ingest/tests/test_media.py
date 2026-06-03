"""Tests for media-processing helpers that do not require ffmpeg/yt-dlp."""

from __future__ import annotations

from pathlib import Path

from ingest.media import MediaProcessor


class _StubProcessor(MediaProcessor):
    """Skip ffmpeg invocation; just exercise the frame-timestamp math."""

    def _run_ffmpeg(self, *args, **kwargs):  # pragma: no cover - never called
        raise AssertionError("unexpected ffmpeg call in stub processor")


def test_extract_frames_centers_timestamps_on_window_midpoint(tmp_path: Path) -> None:
    # Simulate three keyframes ffmpeg already wrote.
    work_dir = tmp_path
    frames_dir = work_dir / "frames"
    frames_dir.mkdir()
    for i in range(1, 4):
        (frames_dir / f"frame_{i:06d}.jpg").write_bytes(b"frame")

    # Monkey-patch the subprocess call by replacing extract_frames body around it:
    # easier to call the real method but skip the ffmpeg `_run` call.
    processor = MediaProcessor(frame_interval_seconds=30, max_frames=20)

    import ingest.media as media

    original_run = media._run
    media._run = lambda args: None  # type: ignore[assignment]
    try:
        frames = processor.extract_frames(tmp_path / "source.mp4", work_dir)
    finally:
        media._run = original_run  # type: ignore[assignment]

    # With interval=30, frame 1 lives in [0,30); midpoint = 15. Frame 2 → 45. Frame 3 → 75.
    assert [round(frame.timestamp_seconds, 3) for frame in frames] == [15.0, 45.0, 75.0]
    # Critically: frame 1 is NOT at t=0 — that was the off-by-half-interval bug.
    assert frames[0].timestamp_seconds != 0


def test_extract_frames_handles_default_short_interval(tmp_path: Path) -> None:
    work_dir = tmp_path
    frames_dir = work_dir / "frames"
    frames_dir.mkdir()
    (frames_dir / "frame_000001.jpg").write_bytes(b"only one")

    processor = MediaProcessor(frame_interval_seconds=10, max_frames=20)

    import ingest.media as media

    original_run = media._run
    media._run = lambda args: None  # type: ignore[assignment]
    try:
        frames = processor.extract_frames(tmp_path / "source.mp4", work_dir)
    finally:
        media._run = original_run  # type: ignore[assignment]

    assert frames[0].timestamp_seconds == 5.0
