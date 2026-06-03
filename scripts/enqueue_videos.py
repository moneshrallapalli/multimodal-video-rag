"""Enqueue YouTube videos for ingestion via DynamoDB + SQS.

Bypasses the admin API auth layer but uses the same code path the API uses.
The Fargate worker picks up jobs from SQS identically.

Usage:
    uv run python scripts/enqueue_videos.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "shared" / "src"))

from shared import settings  # noqa: E402
from shared.ingestion import job_id_for_video, normalize_youtube_url, utc_now_iso  # noqa: E402
from shared.schemas import IngestJobMessage  # noqa: E402

VIDEOS = [
    ("u4ZoJKF_VuA", "Simon Sinek — How Great Leaders Inspire Action (TED)"),
    ("1Gdl-A1DvpA", "Gordon Ramsay — Back-to-Back Chef (Bon Appetit)"),
    ("iCvmsMzlF7o", "Brene Brown — The Power of Vulnerability (TED)"),
    ("TGdLss5Srnk", "Sam Altman on Elon Musk suing OpenAI (Lex Fridman)"),
    ("E76CUtSHMrU", "MKBHD — Smartphone Awards 2024"),
    ("h6fcK_fRYaI", "Kurzgesagt — The Egg (animated)"),
    ("v7AYKMP6rOE", "Yoga With Adriene — Yoga For Complete Beginners"),
    ("Th8JoIan4dg", "YC — How to Get and Evaluate Startup Ideas"),
    ("arj7oStGLkU", "Tim Urban — Inside the Mind of a Master Procrastinator (TED)"),
    ("uxPdPpi5W4o", "Veritasium — Why Are 96M Black Balls on This Reservoir?"),
]

GSI_PARTITION = "all"


def enqueue(video_id: str, label: str) -> str:
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    table = dynamodb.Table(settings.dynamodb_jobs_table)

    normalized = normalize_youtube_url(f"https://youtu.be/{video_id}")
    job_id = job_id_for_video(normalized.video_id)
    now = utc_now_iso()

    item = {
        "job_id": job_id,
        "youtube_url": normalized.youtube_url,
        "video_id": normalized.video_id,
        "title": None,
        "status": "queued",
        "progress": 0,
        "created_at": now,
        "updated_at": now,
        "error": None,
        "gsi_partition": GSI_PARTITION,
    }

    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(job_id)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            existing = table.get_item(Key={"job_id": job_id}).get("Item", {})
            status = existing.get("status", "unknown")
            return f"SKIP (already exists, status={status})"
        raise

    message = IngestJobMessage(
        job_id=job_id,
        video_id=normalized.video_id,
        youtube_url=normalized.youtube_url,
        requested_at=now,
    )
    sqs.send_message(
        QueueUrl=settings.sqs_queue_url,
        MessageBody=message.model_dump_json(),
    )
    return "QUEUED"


def main() -> None:
    if not settings.sqs_queue_url:
        print("ERROR: SQS_QUEUE_URL not set in .env", file=sys.stderr)
        sys.exit(1)

    print(f"Enqueuing {len(VIDEOS)} videos to SQS...")
    print(f"  Queue: {settings.sqs_queue_url}")
    print(f"  Jobs table: {settings.dynamodb_jobs_table}")
    print()

    for video_id, label in VIDEOS:
        result = enqueue(video_id, label)
        print(f"  [{result:8s}] {video_id}  {label}")

    print()
    print("Done. Monitor progress at: https://multimodal-video-rag-web.vercel.app")
    print("Or run: uv run python scripts/check_jobs.py")


if __name__ == "__main__":
    main()
