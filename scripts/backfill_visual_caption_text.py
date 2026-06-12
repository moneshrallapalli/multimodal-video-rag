"""Backfill caption text onto already-indexed visual (image-embedding) vectors.

Frames indexed before captions were added to visual metadata surface as
contentless "Visual frame at 10:05" snippets, which the answer model cannot
ground on. This walks every video's frames.json + captions.json artifact pair
in S3 and merges {"text": caption} into the matching visual vector's metadata.

Usage:
    uv run python scripts/backfill_visual_caption_text.py [--video-id <id>] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import boto3
from shared import settings
from shared.pinecone_client import PineconeIndexClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach caption text to visual vectors")
    parser.add_argument("--bucket", default=settings.s3_bucket)
    parser.add_argument("--video-id", default=None, help="Limit to one video")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.bucket:
        raise SystemExit("--bucket is required when S3_BUCKET is not configured")

    s3 = boto3.client("s3", region_name=settings.aws_region)
    visual_index = None
    if not args.dry_run:
        visual_index = PineconeIndexClient.from_index_name(
            settings.pinecone_visual_index,
            expected_dim=settings.embed_dim,
            expected_metric="cosine",
        )

    summary: list[dict[str, Any]] = []
    for video_id in _video_ids(s3, bucket=args.bucket, only=args.video_id):
        frames = _load_json(s3, args.bucket, f"videos/{video_id}/frames/frames.json")
        captions = _load_json(s3, args.bucket, f"videos/{video_id}/frames/captions.json")
        if not frames or not captions:
            summary.append({"video_id": video_id, "updated": 0, "reason": "missing_artifacts"})
            continue
        if len(frames) != len(captions):
            summary.append(
                {
                    "video_id": video_id,
                    "updated": 0,
                    "reason": f"length_mismatch frames={len(frames)} captions={len(captions)}",
                }
            )
            continue
        updated = 0
        for frame, caption in zip(frames, captions, strict=True):
            text = str(caption).strip()
            if not text:
                continue
            if visual_index is not None:
                visual_index.update_metadata(str(frame["frame_id"]), {"text": text})
            updated += 1
        summary.append({"video_id": video_id, "updated": updated})

    print(json.dumps({"dry_run": args.dry_run, "videos": summary}, indent=2))


def _video_ids(s3: Any, *, bucket: str, only: str | None) -> list[str]:
    if only:
        return [only]
    video_ids: set[str] = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="videos/", Delimiter="/"):
        for prefix in page.get("CommonPrefixes", []):
            video_ids.add(str(prefix["Prefix"]).split("/")[1])
    return sorted(video_ids)


def _load_json(s3: Any, bucket: str, key: str) -> Any | None:
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except Exception:
        return None
    return json.loads(response["Body"].read().decode("utf-8"))


if __name__ == "__main__":
    main()
