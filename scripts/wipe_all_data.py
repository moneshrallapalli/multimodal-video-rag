"""Delete all ingested data: Pinecone vectors, DynamoDB items, and S3 artifacts.

Run this before re-ingesting videos with new settings (e.g. finer frame intervals).

Usage:
    uv run python scripts/wipe_all_data.py --confirm
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "shared" / "src"))

from shared import settings  # noqa: E402


def _pinecone_delete_all(index_name: str) -> int:
    api_key = settings.pinecone_api_key
    if not api_key:
        print(f"  SKIP {index_name} (no PINECONE_API_KEY)")
        return 0

    list_req = Request("https://api.pinecone.io/indexes", headers={"Api-Key": api_key})
    with urlopen(list_req, timeout=30) as resp:
        indexes = json.loads(resp.read().decode())

    host = None
    for idx in indexes.get("indexes", []):
        if idx["name"] == index_name:
            host = idx["host"]
            break
    if not host:
        print(f"  SKIP {index_name} (index not found)")
        return 0

    stats_req = Request(
        f"https://{host}/describe_index_stats",
        data=b"{}",
        headers={"Api-Key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(stats_req, timeout=30) as resp:
        stats = json.loads(resp.read().decode())
    vector_count = stats.get("totalVectorCount", 0)

    delete_req = Request(
        f"https://{host}/vectors/delete",
        data=json.dumps({"deleteAll": True}).encode(),
        headers={"Api-Key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    urlopen(delete_req, timeout=30).read()
    print(f"  Pinecone {index_name}: deleted {vector_count} vectors")
    return vector_count


def _dynamodb_delete_all(table_name: str, key_attr: str) -> int:
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = dynamodb.Table(table_name)
    count = 0
    scan_kwargs: dict = {}
    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={key_attr: item[key_attr]})
                count += 1
        if not response.get("LastEvaluatedKey"):
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    print(f"  DynamoDB {table_name}: deleted {count} items")
    return count


def _s3_delete_prefix(bucket: str, prefix: str) -> int:
    s3 = boto3.client("s3", region_name=settings.aws_region)
    count = 0
    kwargs: dict = {"Bucket": bucket, "Prefix": prefix}
    while True:
        response = s3.list_objects_v2(**kwargs)
        objects = response.get("Contents", [])
        if not objects:
            break
        delete_keys = [{"Key": obj["Key"]} for obj in objects]
        s3.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
        count += len(delete_keys)
        if not response.get("IsTruncated"):
            break
        kwargs["ContinuationToken"] = response["NextContinuationToken"]
    print(f"  S3 s3://{bucket}/{prefix}*: deleted {count} objects")
    return count


def main() -> None:
    if "--confirm" not in sys.argv:
        print("This will DELETE all ingested data (Pinecone, DynamoDB, S3).")
        print("Run with --confirm to proceed.")
        sys.exit(1)

    print("Wiping all data...\n")

    print("[Pinecone]")
    _pinecone_delete_all(settings.pinecone_transcript_index)
    _pinecone_delete_all(settings.pinecone_visual_index)

    print("\n[DynamoDB]")
    if settings.dynamodb_videos_table:
        _dynamodb_delete_all(settings.dynamodb_videos_table, "video_id")
    if settings.dynamodb_jobs_table:
        _dynamodb_delete_all(settings.dynamodb_jobs_table, "job_id")

    print("\n[S3]")
    if settings.s3_bucket:
        _s3_delete_prefix(settings.s3_bucket, "videos/")
        _s3_delete_prefix(settings.s3_bucket, "corpus/")
    else:
        print("  SKIP (no S3_BUCKET configured)")

    print("\nDone. All data wiped. Re-ingest with:")
    print("  uv run python scripts/enqueue_videos.py --force")


if __name__ == "__main__":
    main()
