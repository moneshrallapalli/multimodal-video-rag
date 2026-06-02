"""Phase 2 ingestion worker pipeline."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from shared.ingestion import audio_key, frame_key, metadata_key, transcript_key, utc_now_iso
from shared.schemas import IngestJobMessage, JobStatus, VideoMetadataArtifact

from .media import MediaProcessor, frame_artifacts


class IngestionWorker:
    def __init__(
        self,
        *,
        bucket: str,
        jobs_table: Any,
        videos_table: Any,
        s3_client: Any,
        media: MediaProcessor | None = None,
    ) -> None:
        self.bucket = bucket
        self.jobs_table = jobs_table
        self.videos_table = videos_table
        self.s3 = s3_client
        self.media = media or MediaProcessor()

    def process(self, message: IngestJobMessage) -> None:
        """Process one SQS ingestion message.

        Exceptions are re-raised after the job is marked failed so SQS can retry
        and eventually redrive to the DLQ.
        """
        try:
            self._update_job(message.job_id, status="downloading", progress=10)
            with TemporaryDirectory(prefix=f"ingest-{message.video_id}-") as tmp:
                work_dir = Path(tmp)

                metadata = self.media.fetch_metadata(message.youtube_url)
                self._upload_json(
                    metadata_key(message.video_id), metadata.model_dump_json(indent=2)
                )
                self._update_job(
                    message.job_id,
                    status="downloading",
                    progress=25,
                    title=metadata.title,
                )

                source_path = self.media.download_video(message.youtube_url, work_dir)
                audio_path = self.media.extract_audio(source_path, work_dir)
                self._upload_file(audio_path, audio_key(message.video_id), "audio/mp4")

                frames = self.media.extract_frames(source_path, work_dir)
                frame_keys: list[str] = []
                for index, frame in enumerate(frames, start=1):
                    key = frame_key(message.video_id, index)
                    self._upload_file(frame.path, key, "image/jpeg")
                    frame_keys.append(key)
                self._upload_json(
                    f"videos/{message.video_id}/frames/frames.json",
                    _model_list_json(frame_artifacts(message.video_id, frames, frame_keys)),
                )

                self._update_job(message.job_id, status="transcribing", progress=70)
                transcript = self.media.transcribe_audio(audio_path, message.video_id)
                self._upload_json(
                    transcript_key(message.video_id),
                    transcript.model_dump_json(indent=2),
                )

                self._put_video_record(message, metadata)
                self._update_job(
                    message.job_id,
                    status="completed",
                    progress=100,
                    title=metadata.title,
                    error=None,
                )
        except Exception as exc:
            self._update_job(message.job_id, status="failed", progress=0, error=str(exc)[:500])
            raise

    def _upload_file(self, path: Path, key: str, content_type: str) -> None:
        self.s3.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    def _upload_json(self, key: str, body: str) -> None:
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )

    def _update_job(
        self,
        job_id: str,
        *,
        status: JobStatus,
        progress: int,
        title: str | None = None,
        error: str | None = None,
    ) -> None:
        now = utc_now_iso()
        names = {"#status": "status"}
        values: dict[str, Any] = {
            ":status": status,
            ":progress": progress,
            ":updated_at": now,
        }
        assignments = ["#status = :status", "progress = :progress", "updated_at = :updated_at"]
        if title is not None:
            names["#title"] = "title"
            values[":title"] = title
            assignments.append("#title = :title")
        if error is not None:
            names["#error"] = "error"
            values[":error"] = error
            assignments.append("#error = :error")
        elif status == "completed":
            names["#error"] = "error"
            values[":error"] = None
            assignments.append("#error = :error")

        self.jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=f"SET {', '.join(assignments)}",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def _put_video_record(
        self,
        message: IngestJobMessage,
        metadata: VideoMetadataArtifact,
    ) -> None:
        now = utc_now_iso()
        self.videos_table.put_item(
            Item={
                "video_id": message.video_id,
                "youtube_url": message.youtube_url,
                "title": metadata.title,
                "author": metadata.author,
                "duration_seconds": metadata.duration_seconds,
                "thumbnail_url": metadata.thumbnail_url,
                "artifact_prefix": f"videos/{message.video_id}",
                "status": "ingested",
                "created_at": now,
                "updated_at": now,
            }
        )


def _model_list_json(models: list[Any]) -> str:
    return "[" + ",".join(model.model_dump_json() for model in models) + "]"
