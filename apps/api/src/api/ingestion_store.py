"""Admin ingestion backing store.

Phase 1 used an in-memory mock. Phase 2 keeps the same route contracts, but
uses DynamoDB for job status and SQS for worker handoff whenever `SQS_QUEUE_URL`
is configured. Tests and lightweight local demos can still fall back to mocks.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError
from shared import settings
from shared.ingestion import job_id_for_video, normalize_youtube_url, utc_now_iso
from shared.schemas import IngestJobMessage, IngestResponse, Job, JobsResponse

from . import mock_data

# Constant GSI partition value: keeps all jobs in one queryable bucket without
# needing an extra dimension. Fine at the demo's scale (≤ low hundreds of jobs).
_JOBS_GSI_PARTITION = "all"
_JOBS_GSI_NAME = "JobsByCreatedAt"


def _is_duplicate_job_error(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, int):
        return value
    return default


def _item_to_job(item: dict[str, Any]) -> Job:
    return Job(
        id=str(item["job_id"]),
        youtube_url=str(item["youtube_url"]),
        video_id=item.get("video_id"),
        title=item.get("title"),
        status=item.get("status", "queued"),
        progress=_coerce_int(item.get("progress")),
        created_at=str(item["created_at"]),
        updated_at=str(item["updated_at"]),
        error=item.get("error"),
    )


class DynamoIngestionStore:
    """DynamoDB + SQS implementation for admin ingestion."""

    def __init__(self, *, jobs_table: Any, sqs_client: Any, queue_url: str) -> None:
        self._jobs_table = jobs_table
        self._sqs = sqs_client
        self._queue_url = queue_url

    def list_jobs(self) -> JobsResponse:
        # Query the JobsByCreatedAt GSI to get newest-first ordering with a
        # bounded result set. Fall back to scan if the GSI doesn't exist yet
        # (e.g. an older deployed stack); the fallback can be removed once all
        # environments have been redeployed with T12 infra.
        try:
            response = self._jobs_table.query(
                IndexName=_JOBS_GSI_NAME,
                KeyConditionExpression="gsi_partition = :p",
                ExpressionAttributeValues={":p": _JOBS_GSI_PARTITION},
                ScanIndexForward=False,
                Limit=100,
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ValidationException":
                raise
            response = self._jobs_table.scan(Limit=100)
        jobs = [_item_to_job(item) for item in response.get("Items", [])]
        jobs.sort(key=lambda job: job.created_at, reverse=True)
        return JobsResponse(jobs=jobs)

    def enqueue(self, youtube_url: str) -> IngestResponse:
        normalized = normalize_youtube_url(youtube_url)
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
            # GSI partition: all jobs in one queryable bucket; sort key is created_at.
            "gsi_partition": _JOBS_GSI_PARTITION,
        }

        try:
            self._jobs_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(job_id)",
            )
        except ClientError as exc:
            if not _is_duplicate_job_error(exc):
                raise
            existing = self._jobs_table.get_item(Key={"job_id": job_id}).get("Item")
            if existing:
                return IngestResponse(job=_item_to_job(existing))
            raise

        message = IngestJobMessage(
            job_id=job_id,
            video_id=normalized.video_id,
            youtube_url=normalized.youtube_url,
            requested_at=now,
        )
        self._sqs.send_message(QueueUrl=self._queue_url, MessageBody=message.model_dump_json())
        return IngestResponse(job=_item_to_job(item))


def _dynamo_store() -> DynamoIngestionStore:
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    return DynamoIngestionStore(
        jobs_table=dynamodb.Table(settings.dynamodb_jobs_table),
        sqs_client=sqs,
        queue_url=settings.sqs_queue_url,
    )


def real_ingestion_enabled() -> bool:
    return bool(settings.sqs_queue_url)


def list_jobs() -> JobsResponse:
    if not real_ingestion_enabled():
        return mock_data.list_jobs()
    return _dynamo_store().list_jobs()


def enqueue_ingestion(youtube_url: str) -> IngestResponse:
    if not real_ingestion_enabled():
        return mock_data.add_job(youtube_url)
    return _dynamo_store().enqueue(youtube_url)
