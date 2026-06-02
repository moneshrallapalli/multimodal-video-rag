"""SQS polling behavior for the ingestion worker entrypoint."""

from __future__ import annotations

from ingest.main import SqsWorkerPoller
from shared.schemas import IngestJobMessage


class FakeSqs:
    def __init__(self, messages):
        self.messages = messages
        self.deleted: list[str] = []

    def receive_message(self, **kwargs):
        assert kwargs["QueueUrl"] == "queue-url"
        return {"Messages": self.messages}

    def delete_message(self, *, QueueUrl: str, ReceiptHandle: str) -> None:
        assert QueueUrl == "queue-url"
        self.deleted.append(ReceiptHandle)


class FakeWorker:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.processed: list[IngestJobMessage] = []

    def process(self, message: IngestJobMessage) -> None:
        self.processed.append(message)
        if self.fail:
            raise RuntimeError("boom")


def _raw_message():
    body = IngestJobMessage(
        job_id="yt_QkdBXUikRQc",
        video_id="QkdBXUikRQc",
        youtube_url="https://youtu.be/QkdBXUikRQc",
        requested_at="2026-06-02T12:00:00+00:00",
    ).model_dump_json()
    return {"MessageId": "m1", "Body": body, "ReceiptHandle": "receipt-1"}


def test_poller_deletes_message_after_success():
    sqs = FakeSqs([_raw_message()])
    worker = FakeWorker()
    poller = SqsWorkerPoller(queue_url="queue-url", sqs_client=sqs, worker=worker)

    assert poller.run_once() is True

    assert worker.processed[0].video_id == "QkdBXUikRQc"
    assert sqs.deleted == ["receipt-1"]


def test_poller_leaves_failed_message_for_retry():
    sqs = FakeSqs([_raw_message()])
    worker = FakeWorker(fail=True)
    poller = SqsWorkerPoller(queue_url="queue-url", sqs_client=sqs, worker=worker)

    assert poller.run_once() is True

    assert worker.processed[0].job_id == "yt_QkdBXUikRQc"
    assert sqs.deleted == []


def test_poller_returns_false_when_queue_is_empty():
    poller = SqsWorkerPoller(queue_url="queue-url", sqs_client=FakeSqs([]), worker=FakeWorker())

    assert poller.run_once() is False
