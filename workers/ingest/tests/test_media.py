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


def test_parse_showinfo_times_extracts_pts():
    from ingest.media import _parse_showinfo_times

    stderr = (
        "[Parsed_showinfo_1 @ 0x600] n:   0 pts:  12345 pts_time:12.345 duration:0.04\n"
        "[Parsed_showinfo_1 @ 0x600] n:   1 pts:  45000 pts_time:45 duration:0.04\n"
    )
    assert _parse_showinfo_times(stderr) == [12.345, 45.0]
    assert _parse_showinfo_times("") == []


def test_dedupe_collapses_near_identical_neighbors(tmp_path: Path) -> None:
    """A static shot collapses to its first frame; a visual change starts a new run."""
    from ingest.media import FrameFile, _dedupe_near_duplicates
    from PIL import Image

    flat_a = tmp_path / "a.jpg"
    Image.new("L", (32, 32), 128).save(flat_a)
    flat_b = tmp_path / "b.jpg"
    Image.new("L", (32, 32), 130).save(flat_b)
    gradient = Image.new("L", (32, 32))
    gradient.putdata([max(0, 255 - x * 8) for _y in range(32) for x in range(32)])
    distinct = tmp_path / "c.jpg"
    gradient.save(distinct)

    frames = [
        FrameFile(path=flat_a, timestamp_seconds=5.0),
        FrameFile(path=flat_b, timestamp_seconds=15.0),
        FrameFile(path=distinct, timestamp_seconds=25.0),
    ]
    deduped = _dedupe_near_duplicates(frames, max_distance=6)

    assert [frame.timestamp_seconds for frame in deduped] == [5.0, 25.0]


def test_dedupe_keeps_unreadable_frames(tmp_path: Path) -> None:
    from ingest.media import FrameFile, _dedupe_near_duplicates

    broken = tmp_path / "broken.jpg"
    broken.write_bytes(b"not an image")
    frames = [FrameFile(path=broken, timestamp_seconds=5.0)]

    assert _dedupe_near_duplicates(frames, max_distance=6) == frames


def test_cap_frames_subsamples_evenly() -> None:
    from ingest.media import FrameFile, _cap_frames

    frames = [FrameFile(path=Path(f"f{i}.jpg"), timestamp_seconds=float(i * 10)) for i in range(10)]
    capped = _cap_frames(frames, 4)

    # Even spread across the whole video, not just the first N frames.
    assert [frame.timestamp_seconds for frame in capped] == [0.0, 30.0, 60.0, 90.0]
    assert _cap_frames(frames, 20) == frames


def test_scene_frames_pair_pts_times_with_files(tmp_path: Path) -> None:
    import ingest.media as media

    processor = MediaProcessor(scene_threshold=0.3)

    class FakeProc:
        stderr = "pts_time:1.5 selected\npts_time:88.25 selected\n"

    def fake_run(args):
        scene_dir = tmp_path / "scene_frames"
        (scene_dir / "scene_000001.jpg").write_bytes(b"x")
        (scene_dir / "scene_000002.jpg").write_bytes(b"x")
        return FakeProc()

    original_run = media._run
    media._run = fake_run  # type: ignore[assignment]
    try:
        frames = processor._extract_scene_frames(tmp_path / "src.mp4", tmp_path)
    finally:
        media._run = original_run  # type: ignore[assignment]

    assert [(frame.path.name, frame.timestamp_seconds) for frame in frames] == [
        ("scene_000001.jpg", 1.5),
        ("scene_000002.jpg", 88.25),
    ]
