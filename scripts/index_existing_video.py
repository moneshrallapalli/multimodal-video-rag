"""Index existing Phase 2 S3 artifacts into Pinecone.

Usage:
    uv run python scripts/index_existing_video.py QkdBXUikRQc
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import boto3
from ingest.indexing import VideoIndexer
from ingest.media import FrameFile
from shared import settings
from shared.ingestion import artifact_prefix, metadata_key, transcript_key
from shared.schemas import FrameArtifact, TranscriptArtifact, VideoMetadataArtifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Index existing S3 video artifacts into Pinecone")
    parser.add_argument("video_id", help="YouTube video id to index")
    args = parser.parse_args()

    if not settings.s3_bucket:
        raise RuntimeError("S3_BUCKET is required")

    s3 = boto3.client("s3", region_name=settings.aws_region)
    metadata = VideoMetadataArtifact.model_validate_json(_get_text(s3, metadata_key(args.video_id)))
    transcript = TranscriptArtifact.model_validate_json(
        _get_text(s3, transcript_key(args.video_id))
    )
    frame_artifacts = [
        FrameArtifact.model_validate(item)
        for item in json.loads(
            _get_text(s3, f"{artifact_prefix(args.video_id)}/frames/frames.json")
        )
    ]

    with TemporaryDirectory(prefix=f"index-{args.video_id}-") as tmp:
        frame_files: list[FrameFile] = []
        frame_keys: list[str] = []
        for index, artifact in enumerate(frame_artifacts, start=1):
            path = Path(tmp) / f"frame_{index:06d}.jpg"
            s3.download_file(settings.s3_bucket, artifact.s3_key, str(path))
            frame_files.append(FrameFile(path=path, timestamp_seconds=artifact.timestamp_seconds))
            frame_keys.append(artifact.s3_key)

        summary = VideoIndexer.from_settings(bucket=settings.s3_bucket).index_video(
            metadata=metadata,
            transcript=transcript,
            frames=frame_files,
            frame_keys=frame_keys,
        )

    print(summary.model_dump_json(indent=2))


def _get_text(s3, key: str) -> str:
    response = s3.get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read().decode("utf-8")


if __name__ == "__main__":
    main()
