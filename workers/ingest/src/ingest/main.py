"""Ingestion worker entrypoint, run locally or as a Fargate task."""

from __future__ import annotations

import logging

import boto3
from shared import settings
from shared.schemas import IngestJobMessage

from .indexing import VideoIndexer
from .media import MediaProcessor
from .pipeline import IngestionWorker

logger = logging.getLogger(__name__)


class SqsWorkerPoller:
    def __init__(self, *, queue_url: str, sqs_client, worker: IngestionWorker) -> None:
        self.queue_url = queue_url
        self.sqs = sqs_client
        self.worker = worker

    def run_once(self) -> bool:
        response = self.sqs.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
            VisibilityTimeout=900,
        )
        messages = response.get("Messages", [])
        if not messages:
            logger.info("worker_poll_empty queue_url=%s", self.queue_url)
            return False

        for raw in messages:
            message_id = raw.get("MessageId", "<unknown>")
            payload = IngestJobMessage.model_validate_json(raw["Body"])
            logger.info(
                "Processing ingestion message %s for video %s", message_id, payload.video_id
            )
            try:
                self.worker.process(payload)
            except Exception:
                logger.exception(
                    "Ingestion message %s failed; leaving it on SQS for retry", message_id
                )
                continue
            self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=raw["ReceiptHandle"])
        return True


def build_poller() -> SqsWorkerPoller:
    if not settings.sqs_queue_url:
        raise RuntimeError("SQS_QUEUE_URL is required to run the ingestion worker")
    if not settings.s3_bucket:
        raise RuntimeError("S3_BUCKET is required to run the ingestion worker")

    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    s3 = boto3.client("s3", region_name=settings.aws_region)
    worker = IngestionWorker(
        bucket=settings.s3_bucket,
        jobs_table=dynamodb.Table(settings.dynamodb_jobs_table),
        videos_table=dynamodb.Table(settings.dynamodb_videos_table),
        s3_client=s3,
        media=MediaProcessor(
            frame_interval_seconds=settings.ingest_frame_interval_seconds,
            max_frames=settings.ingest_max_frames,
            whisper_model_size=settings.whisper_model_size,
        ),
        indexer=VideoIndexer.from_settings(bucket=settings.s3_bucket),
    )
    return SqsWorkerPoller(queue_url=settings.sqs_queue_url, sqs_client=sqs, worker=worker)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    poller = build_poller()
    processed = 0
    logger.info("worker_start queue_url=%s", poller.queue_url)
    while poller.run_once():
        processed += 1
    logger.info("worker_exit messages_processed=%s", processed)


if __name__ == "__main__":
    main()
