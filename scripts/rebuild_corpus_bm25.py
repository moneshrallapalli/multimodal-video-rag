"""Rebuild the corpus-wide BM25 stats artifact from transcripts in S3.

Usage:
    uv run python scripts/rebuild_corpus_bm25.py --bucket <artifacts-bucket>
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import boto3
from shared import settings
from shared.bm25 import BM25Encoder
from shared.indexing import chunk_transcript
from shared.ingestion import corpus_bm25_stats_key
from shared.schemas import TranscriptArtifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild corpus BM25 stats from S3 transcripts")
    parser.add_argument("--bucket", default=settings.s3_bucket)
    parser.add_argument("--chunk-seconds", type=int, default=settings.transcript_chunk_seconds)
    parser.add_argument(
        "--overlap-seconds",
        type=int,
        default=settings.transcript_chunk_overlap_seconds,
    )
    args = parser.parse_args()
    if not args.bucket:
        raise SystemExit("--bucket is required when S3_BUCKET is not configured")

    s3_client = boto3.client("s3", region_name=settings.aws_region)
    result = rebuild_corpus_bm25(
        bucket=args.bucket,
        s3_client=s3_client,
        chunk_seconds=args.chunk_seconds,
        overlap_seconds=args.overlap_seconds,
    )
    print(json.dumps(result, indent=2))


def rebuild_corpus_bm25(
    *,
    bucket: str,
    s3_client: Any,
    chunk_seconds: int,
    overlap_seconds: int,
) -> dict[str, Any]:
    documents: list[str] = []
    video_ids: set[str] = set()
    for transcript in _iter_transcripts(bucket=bucket, s3_client=s3_client):
        video_ids.add(transcript.video_id)
        chunks = chunk_transcript(
            transcript,
            target_seconds=chunk_seconds,
            overlap_seconds=overlap_seconds,
        )
        documents.extend(chunk.text for chunk in chunks)
    if not documents:
        raise RuntimeError("No transcript artifacts found in S3")

    encoder = BM25Encoder.fit(documents)
    key = corpus_bm25_stats_key()
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(encoder.to_dict()).encode("utf-8"),
        ContentType="application/json",
    )
    return {
        "bucket": bucket,
        "key": key,
        "videos": len(video_ids),
        "chunks": len(documents),
        "video_ids": sorted(video_ids),
    }


def _iter_transcripts(*, bucket: str, s3_client: Any):
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="videos/"):
        for obj in page.get("Contents", []):
            key = str(obj.get("Key", ""))
            if not key.endswith("/transcript/transcript.json"):
                continue
            response = s3_client.get_object(Bucket=bucket, Key=key)
            yield TranscriptArtifact.model_validate_json(response["Body"].read().decode("utf-8"))


if __name__ == "__main__":
    main()
