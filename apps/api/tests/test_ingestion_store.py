"""Unit coverage for the real-shaped DynamoDB/SQS ingestion store."""

from __future__ import annotations

import json
from typing import Any

from api.ingestion_store import DynamoIngestionStore, _item_to_job
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

    def query(
        self,
        *,
        IndexName: str,
        KeyConditionExpression: str,
        ExpressionAttributeValues: dict[str, Any],
        ScanIndexForward: bool,
        Limit: int,
    ) -> dict[str, Any]:
        assert IndexName == "JobsByCreatedAt"
        assert KeyConditionExpression == "gsi_partition = :p"
        assert ExpressionAttributeValues == {":p": "all"}
        assert ScanIndexForward is False
        assert Limit == 100
        partition = ExpressionAttributeValues[":p"]
        matched = [item for item in self.items.values() if item.get("gsi_partition") == partition]
        matched.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return {"Items": matched}


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
    assert response.job.stage == "queued"
    assert response.job.stages_seen == ["queued"]
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


def test_enqueued_jobs_carry_gsi_partition_value_for_created_at_index():
    """The JobsByCreatedAt GSI requires a constant partition value on every
    item — without it the new jobs would never appear in the indexed listing."""
    table = FakeJobsTable()
    sqs = FakeSqs()
    store = DynamoIngestionStore(jobs_table=table, sqs_client=sqs, queue_url="queue-url")

    store.enqueue("https://youtu.be/QkdBXUikRQc")

    stored = next(iter(table.items.values()))
    assert stored["gsi_partition"] == "all"


def test_list_jobs_falls_back_to_scan_when_gsi_missing():
    """Older deployed stacks won't have the GSI yet. The store falls back to a
    scan so the admin console still works during the deploy window."""

    class GsiMissingTable(FakeJobsTable):
        def query(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "ValidationException"}},
                "Query",
            )

    table = GsiMissingTable()
    sqs = FakeSqs()
    store = DynamoIngestionStore(jobs_table=table, sqs_client=sqs, queue_url="queue-url")
    store.enqueue("https://youtu.be/QkdBXUikRQc")

    jobs = store.list_jobs().jobs

    assert len(jobs) == 1


def test_item_to_job_reads_legacy_items_without_stage():
    job = _item_to_job(
        {
            "job_id": "yt_legacy",
            "youtube_url": "https://youtu.be/legacy",
            "video_id": "legacy",
            "status": "completed",
            "progress": 100,
            "created_at": "2026-06-01T10:00:00+00:00",
            "updated_at": "2026-06-01T11:00:00+00:00",
        }
    )

    assert job.stage is None
    assert job.stages_seen == []
