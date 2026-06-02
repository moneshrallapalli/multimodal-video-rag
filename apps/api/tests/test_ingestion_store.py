"""Unit coverage for the real-shaped DynamoDB/SQS ingestion store."""

from __future__ import annotations

import json
from typing import Any

from api.ingestion_store import DynamoIngestionStore
from botocore.exceptions import ClientError


class FakeJobsTable:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def put_item(self, *, Item: dict[str, Any], ConditionExpression: str) -> None:
        assert ConditionExpression == "attribute_not_exists(job_id)"
        job_id = Item["job_id"]
        if job_id in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}},
                "PutItem",
            )
        self.items[job_id] = dict(Item)

    def get_item(self, *, Key: dict[str, str]) -> dict[str, Any]:
        item = self.items.get(Key["job_id"])
        return {"Item": item} if item else {}

    def scan(self, *, Limit: int) -> dict[str, Any]:
        assert Limit == 100
        return {"Items": list(self.items.values())}


class FakeSqs:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send_message(self, *, QueueUrl: str, MessageBody: str) -> None:
        self.messages.append({"QueueUrl": QueueUrl, "MessageBody": MessageBody})


def test_enqueue_writes_job_and_sends_sqs_message():
    table = FakeJobsTable()
    sqs = FakeSqs()
    store = DynamoIngestionStore(jobs_table=table, sqs_client=sqs, queue_url="queue-url")

    response = store.enqueue("https://www.youtube.com/watch?v=QkdBXUikRQc&t=30s")

    assert response.job.id == "yt_QkdBXUikRQc"
    assert response.job.video_id == "QkdBXUikRQc"
    assert response.job.youtube_url == "https://youtu.be/QkdBXUikRQc"
    assert response.job.status == "queued"
    assert response.job.progress == 0
    assert len(sqs.messages) == 1

    message = json.loads(sqs.messages[0]["MessageBody"])
    assert sqs.messages[0]["QueueUrl"] == "queue-url"
    assert message["job_id"] == "yt_QkdBXUikRQc"
    assert message["video_id"] == "QkdBXUikRQc"
    assert message["youtube_url"] == "https://youtu.be/QkdBXUikRQc"


def test_enqueue_duplicate_returns_existing_job_without_new_message():
    table = FakeJobsTable()
    sqs = FakeSqs()
    store = DynamoIngestionStore(jobs_table=table, sqs_client=sqs, queue_url="queue-url")

    first = store.enqueue("https://youtu.be/QkdBXUikRQc")
    second = store.enqueue("https://youtu.be/QkdBXUikRQc")

    assert second.job == first.job
    assert len(sqs.messages) == 1


def test_list_jobs_sorts_newest_first():
    table = FakeJobsTable()
    sqs = FakeSqs()
    store = DynamoIngestionStore(jobs_table=table, sqs_client=sqs, queue_url="queue-url")

    older = store.enqueue("https://youtu.be/QkdBXUikRQc").job
    newer = store.enqueue("https://youtu.be/DVtcZQ2QdBg").job
    table.items[older.id]["created_at"] = "2026-06-01T10:00:00+00:00"
    table.items[newer.id]["created_at"] = "2026-06-01T11:00:00+00:00"

    jobs = store.list_jobs().jobs

    assert [job.id for job in jobs] == [newer.id, older.id]
