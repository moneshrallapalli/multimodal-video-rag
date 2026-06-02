"""Media processing steps for Phase 2 ingestion."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from shared.schemas import (
    FrameArtifact,
    TranscriptArtifact,
    TranscriptSegment,
    VideoMetadataArtifact,
)


@dataclass(frozen=True)
class FrameFile:
    path: Path
    timestamp_seconds: float


class MediaProcessor:
    """Thin wrappers around yt-dlp, ffmpeg, and faster-whisper."""

    def __init__(
        self,
        *,
        frame_interval_seconds: int = 30,
        max_frames: int = 20,
        whisper_model_size: str = "tiny.en",
    ) -> None:
        self.frame_interval_seconds = frame_interval_seconds
        self.max_frames = max_frames
        self.whisper_model_size = whisper_model_size

    def fetch_metadata(self, youtube_url: str) -> VideoMetadataArtifact:
        result = _run(
            [
                "yt-dlp",
                "--dump-single-json",
                "--skip-download",
                "--no-playlist",
                youtube_url,
            ]
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
                "yt-dlp",
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
        return [
            FrameFile(path=path, timestamp_seconds=(index - 1) * self.frame_interval_seconds)
            for index, path in enumerate(sorted(frames_dir.glob("frame_*.jpg")), start=1)
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


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, capture_output=True, text=True)
