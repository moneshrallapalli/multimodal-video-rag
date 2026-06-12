"""Media processing steps for Phase 2 ingestion."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from shared.schemas import (
    FrameArtifact,
    TranscriptArtifact,
    TranscriptSegment,
    VideoMetadataArtifact,
)

logger = logging.getLogger(__name__)

_COOKIES_PATH = Path("/tmp/yt-cookies.txt")


@dataclass(frozen=True)
class FrameFile:
    path: Path
    timestamp_seconds: float


def _ytdlp_base_args() -> list[str]:
    args = ["yt-dlp", "--remote-components", "ejs:github"]
    if _COOKIES_PATH.exists():
        args.extend(["--cookies", str(_COOKIES_PATH)])
    return args


def fetch_cookies_from_s3(*, bucket: str, region: str) -> None:
    """Download YouTube cookies from S3 if available."""
    import boto3

    key = "config/youtube-cookies.txt"
    try:
        s3 = boto3.client("s3", region_name=region)
        s3.download_file(bucket, key, str(_COOKIES_PATH))
        logger.info("youtube_cookies_loaded bucket=%s key=%s", bucket, key)
    except Exception:
        logger.info("youtube_cookies_not_found bucket=%s key=%s", bucket, key)


class MediaProcessor:
    """Thin wrappers around yt-dlp, ffmpeg, and faster-whisper."""

    def __init__(
        self,
        *,
        frame_interval_seconds: int = 10,
        max_frames: int = 200,
        whisper_model_size: str = "tiny.en",
        scene_threshold: float = 0.3,
        dedupe_hash_distance: int = 6,
    ) -> None:
        self.frame_interval_seconds = frame_interval_seconds
        self.max_frames = max_frames
        self.whisper_model_size = whisper_model_size
        # Scene-change frames (ffmpeg `select=gt(scene,thr)`) capture cuts the
        # fixed interval misses; <= 0 disables the scene pass.
        self.scene_threshold = scene_threshold
        # Frames whose dHash is within this Hamming distance of the previously
        # kept frame are dropped as near-duplicates (talking-head videos
        # collapse dramatically, cutting caption/embed spend); < 0 disables.
        self.dedupe_hash_distance = dedupe_hash_distance

    def fetch_metadata(self, youtube_url: str) -> VideoMetadataArtifact:
        result = _run(
            [
                *_ytdlp_base_args(),
                "--dump-single-json",
                "--skip-download",
                "--no-playlist",
                youtube_url,
            ],
            capture_stdout=True,
        )
        raw = json.loads(result.stdout)
        duration = raw.get("duration")
        return VideoMetadataArtifact(
            video_id=str(raw["id"]),
            youtube_url=f"https://youtu.be/{raw['id']}",
            title=raw.get("title"),
            author=raw.get("uploader") or raw.get("channel"),
            duration_seconds=int(duration) if isinstance(duration, int | float) else None,
            thumbnail_url=raw.get("thumbnail"),
        )

    def download_video(self, youtube_url: str, work_dir: Path) -> Path:
        output_template = str(work_dir / "source.%(ext)s")
        _run(
            [
                *_ytdlp_base_args(),
                "--no-playlist",
                "-f",
                "bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480][ext=mp4]/best[height<=480]",
                "--merge-output-format",
                "mp4",
                "-o",
                output_template,
                youtube_url,
            ]
        )
        candidates = sorted(work_dir.glob("source.*"))
        if not candidates:
            raise RuntimeError("yt-dlp completed but no source media file was produced")
        return candidates[0]

    def extract_audio(self, source_path: Path, work_dir: Path) -> Path:
        audio_path = work_dir / "audio.m4a"
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(audio_path),
            ]
        )
        return audio_path

    def extract_frames(self, source_path: Path, work_dir: Path) -> list[FrameFile]:
        """Interval coverage + scene-cut frames, deduped by perceptual hash.

        Interval sampling guarantees coverage of static content (talking
        heads); the scene pass catches cuts between samples. dHash dedupe then
        collapses near-identical neighbors so caption/embed cost tracks visual
        variety, not video length.
        """
        interval_frames = self._extract_interval_frames(source_path, work_dir)
        scene_frames = self._extract_scene_frames(source_path, work_dir)
        merged = sorted(interval_frames + scene_frames, key=lambda f: f.timestamp_seconds)
        deduped = _dedupe_near_duplicates(merged, max_distance=self.dedupe_hash_distance)
        return _cap_frames(deduped, self.max_frames)

    def _extract_interval_frames(self, source_path: Path, work_dir: Path) -> list[FrameFile]:
        frames_dir = work_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(frames_dir / "frame_%06d.jpg")
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-vf",
                f"fps=1/{self.frame_interval_seconds}",
                "-frames:v",
                str(self.max_frames),
                output_template,
            ]
        )
        half_interval = self.frame_interval_seconds / 2.0
        return [
            FrameFile(
                path=path,
                timestamp_seconds=(index - 1) * self.frame_interval_seconds + half_interval,
            )
            for index, path in enumerate(sorted(frames_dir.glob("frame_*.jpg")), start=1)
        ]

    def _extract_scene_frames(self, source_path: Path, work_dir: Path) -> list[FrameFile]:
        if self.scene_threshold <= 0:
            return []
        scene_dir = work_dir / "scene_frames"
        scene_dir.mkdir(parents=True, exist_ok=True)
        proc = _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-vf",
                f"select='gt(scene,{self.scene_threshold})',showinfo",
                "-fps_mode",
                "vfr",
                "-frames:v",
                str(self.max_frames),
                str(scene_dir / "scene_%06d.jpg"),
            ]
        )
        # showinfo logs one line per selected frame; pts_time is the frame's
        # exact presentation timestamp (no midpoint correction needed).
        times = _parse_showinfo_times(getattr(proc, "stderr", "") or "")
        paths = sorted(scene_dir.glob("scene_*.jpg"))
        return [
            FrameFile(path=path, timestamp_seconds=ts)
            for path, ts in zip(paths, times, strict=False)
        ]

    def transcribe_audio(self, audio_path: Path, video_id: str) -> TranscriptArtifact:
        from faster_whisper import WhisperModel

        model = WhisperModel(self.whisper_model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio_path))
        return TranscriptArtifact(
            video_id=video_id,
            language=getattr(info, "language", None),
            segments=[
                TranscriptSegment(
                    start_seconds=float(segment.start),
                    end_seconds=float(segment.end),
                    text=segment.text.strip(),
                )
                for segment in segments
            ],
        )


def frame_artifacts(video_id: str, frames: list[FrameFile], keys: list[str]) -> list[FrameArtifact]:
    return [
        FrameArtifact(
            frame_id=f"{video_id}:frame:{index:06d}",
            video_id=video_id,
            timestamp_seconds=frame.timestamp_seconds,
            s3_key=key,
        )
        for index, (frame, key) in enumerate(zip(frames, keys, strict=True), start=1)
    ]


_SHOWINFO_PTS_RE = re.compile(r"pts_time:\s*([0-9]+(?:\.[0-9]+)?)")


def _parse_showinfo_times(stderr: str) -> list[float]:
    """Pull per-frame presentation timestamps out of ffmpeg showinfo logging."""
    return [float(match) for match in _SHOWINFO_PTS_RE.findall(stderr)]


def _dhash(path: Path) -> int:
    """64-bit difference hash: gradient signs of a 9x8 grayscale downscale."""
    from PIL import Image

    with Image.open(path) as image:
        pixels = list(image.convert("L").resize((9, 8)).getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def _dedupe_near_duplicates(frames: list[FrameFile], *, max_distance: int) -> list[FrameFile]:
    """Drop frames perceptually close to the previously kept frame.

    Sequential comparison (not all-pairs) is the right shape for video: a
    static shot collapses to its first frame, while any visual change past the
    Hamming threshold starts a new run. Unreadable images are kept — better a
    duplicate caption than a silently dropped frame.
    """
    if max_distance < 0:
        return frames
    kept: list[FrameFile] = []
    last_hash: int | None = None
    for frame in frames:
        try:
            digest = _dhash(frame.path)
        except Exception:
            logger.warning("frame_dhash_unreadable path=%s", frame.path.name)
            kept.append(frame)
            last_hash = None
            continue
        if last_hash is not None and (digest ^ last_hash).bit_count() <= max_distance:
            continue
        kept.append(frame)
        last_hash = digest
    return kept


def _cap_frames(frames: list[FrameFile], max_frames: int) -> list[FrameFile]:
    """Evenly subsample down to the cap so coverage survives, not just the head."""
    if len(frames) <= max_frames:
        return frames
    if max_frames <= 1:
        return frames[:max_frames]
    step = (len(frames) - 1) / (max_frames - 1)
    indices = sorted({round(i * step) for i in range(max_frames)})
    return [frames[i] for i in indices]


_STDERR_TAIL_BYTES = 4096


def _run(args: list[str], *, capture_stdout: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a subprocess without buffering its stdout in memory by default."""
    proc = subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-_STDERR_TAIL_BYTES:]
        logger.error("subprocess_failed cmd=%s rc=%d stderr=%s", args[0], proc.returncode, tail)
        raise RuntimeError(f"{args[0]} exited {proc.returncode}: {tail}")
    return proc
