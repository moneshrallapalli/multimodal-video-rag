"""Check ingestion job status from DynamoDB.

Usage:
    uv run python scripts/check_jobs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "shared" / "src"))

from shared import settings  # noqa: E402


def main() -> None:
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = dynamodb.Table(settings.dynamodb_jobs_table)

    response = table.scan(Limit=100)
    items = sorted(response.get("Items", []), key=lambda x: x.get("created_at", ""), reverse=True)

    completed = sum(1 for i in items if i.get("status") == "completed")
    queued = sum(1 for i in items if i.get("status") == "queued")
    processing = sum(1 for i in items if i.get("status") == "processing")
    failed = sum(1 for i in items if i.get("status") == "failed")

    print(
        f"Jobs: {len(items)} total | {completed} completed | "
        f"{processing} processing | {queued} queued | {failed} failed"
    )
    print()

    for item in items:
        vid = item.get("video_id", "?")
        status = item.get("status", "?")
        progress = int(item.get("progress", 0))
        title = item.get("title") or "(pending)"
        error = item.get("error", "")

        icon = {"completed": "+", "processing": "~", "queued": ".", "failed": "!"}.get(status, "?")
        line = f"  [{icon}] {vid:13s} {status:10s} {progress:3d}%  {title[:50]}"
        if error:
            line += f"  ERR: {error[:60]}"
        print(line)


if __name__ == "__main__":
    main()
