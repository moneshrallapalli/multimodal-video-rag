"""Phase 2 ingestion worker pipeline."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from shared.bm25 import BM25Encoder
from shared.ingestion import (
    artifact_prefix,
    audio_key,
    bm25_stats_key,
    corpus_bm25_stats_key,
    frame_key,
    metadata_key,
    transcript_key,
    utc_now_iso,
)
from shared.schemas import (
    IndexingSummary,
    IngestJobMessage,
    JobStatus,
    TranscriptArtifact,
    VideoArtifactStats,
    VideoMetadataArtifact,
)

from .captioning import FrameCaptioner
from .indexing import VideoIndexer
from .media import MediaProcessor, frame_artifacts

logger = logging.getLogger(__name__)


class IngestionWorker:
    def __init__(
        self,
        *,
        bucket: str,
        jobs_table: Any,
        videos_table: Any,
        s3_client: Any,
        media: MediaProcessor | None = None,
        indexer: VideoIndexer | None = None,
        captioner: FrameCaptioner | None = None,
    ) -> None:
        self.bucket = bucket
        self.jobs_table = jobs_table
        self.videos_table = videos_table
        self.s3 = s3_client
        self.media = media or MediaProcessor()
        self.indexer = indexer
        self.captioner = captioner

    def process(self, message: IngestJobMessage) -> None:
        """Process one SQS ingestion message.

        Exceptions are re-raised after the job is marked failed so SQS can retry
        and eventually redrive to the DLQ. SQS delivery is at-least-once, so a
        redelivered already-completed job is skipped to avoid re-downloading,
        re-transcribing, and re-embedding (cost + time).
        """
        if self._already_completed(message.job_id):
            return
        media = self._media_for(message)
        try:
            self._update_job(message.job_id, status="downloading", progress=10)
            with TemporaryDirectory(prefix=f"ingest-{message.video_id}-") as tmp:
                work_dir = Path(tmp)

                metadata = media.fetch_metadata(message.youtube_url)
                self._upload_json(
                    metadata_key(message.video_id), metadata.model_dump_json(indent=2)
                )
                self._update_job(
                    message.job_id,
                    status="downloading",
                    progress=25,
                    title=metadata.title,
                )

                source_path = media.download_video(message.youtube_url, work_dir)
                audio_path = media.extract_audio(source_path, work_dir)
                self._upload_file(audio_path, audio_key(message.video_id), "audio/mp4")

                frames = media.extract_frames(source_path, work_dir)
                frame_keys: list[str] = []
                for index, frame in enumerate(frames, start=1):
                    key = frame_key(message.video_id, index)
                    self._upload_file(frame.path, key, "image/jpeg")
                    frame_keys.append(key)
                self._upload_json(
                    f"videos/{message.video_id}/frames/frames.json",
                    _model_list_json(frame_artifacts(message.video_id, frames, frame_keys)),
                )

                captions: list[str] | None = None
                if self.captioner and frames:
                    captions = self.captioner.caption_frames([f.path for f in frames])
                    self._upload_json(
                        f"videos/{message.video_id}/frames/captions.json",
                        json.dumps(captions, indent=2),
                    )

                self._update_job(message.job_id, status="transcribing", progress=70)
                transcript = media.transcribe_audio(audio_path, message.video_id)
                self._upload_json(
                    transcript_key(message.video_id),
                    transcript.model_dump_json(indent=2),
                )

                summary: IndexingSummary | None = None
                if self.indexer:
                    self._update_job(message.job_id, status="embedding", progress=85)
                    summary = self.indexer.index_video(
                        metadata=metadata,
                        transcript=transcript,
                        frames=frames,
                        frame_keys=frame_keys,
                        captions=captions,
                    )
                    self._upload_json(
                        f"{artifact_prefix(message.video_id)}/vectors/indexing_summary.json",
                        summary.model_dump_json(indent=2),
                    )
                    if summary.bm25_stats:
                        # Persist the fitted BM25 stats so query-time hybrid
                        # retrieval can re-encode user queries without re-reading
                        # the transcript corpus.
                        self._upload_json(
                            bm25_stats_key(message.video_id),
                            json.dumps(summary.bm25_stats),
                        )
                        self._refresh_corpus_bm25_stats()

                self._put_video_record(
                    message,
                    metadata,
                    transcript=transcript,
                    visual_frame_count=len(frames),
                    frame_interval_seconds=self._frame_interval_seconds(media, message),
                    indexing_summary=summary,
                )
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

    def _media_for(self, message: IngestJobMessage) -> MediaProcessor:
        if message.frame_interval_seconds is None and message.max_frames is None:
            return self.media
        interval = message.frame_interval_seconds or self.media.frame_interval_seconds
        return MediaProcessor(
            frame_interval_seconds=interval,
            max_frames=message.max_frames or self.media.max_frames,
            whisper_model_size=self.media.whisper_model_size,
        )

    def _frame_interval_seconds(self, media: MediaProcessor, message: IngestJobMessage) -> int:
        if message.frame_interval_seconds is not None:
            return message.frame_interval_seconds
        value = getattr(media, "frame_interval_seconds", None)
        if isinstance(value, int):
            return value
        value = getattr(self.media, "frame_interval_seconds", None)
        return value if isinstance(value, int) else 10

    def _already_completed(self, job_id: str) -> bool:
        """Cheap pre-check: if SQS redelivered a finished job, skip re-doing the
        whole pipeline. Failures during the get_item itself are swallowed so we
        fall through to the normal flow (better to redo work than block on a
        transient DDB read)."""
        try:
            response = self.jobs_table.get_item(Key={"job_id": job_id})
        except Exception:
            logger.exception(
                "worker_job_lookup_error job_id=%s; proceeding with full process", job_id
            )
            return False
        item = response.get("Item") if isinstance(response, dict) else None
        if item and item.get("status") == "completed":
            logger.info("worker_skip_completed_job job_id=%s reason=idempotent_redelivery", job_id)
            return True
        return False

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
        *,
        transcript: TranscriptArtifact,
        visual_frame_count: int,
        frame_interval_seconds: int,
        indexing_summary: IndexingSummary | None,
    ) -> None:
        now = utc_now_iso()
        artifact_stats = VideoArtifactStats(
            transcript_segments=len(transcript.segments),
            transcript_chunks=(
                indexing_summary.transcript_vectors if indexing_summary is not None else None
            ),
            visual_frames=visual_frame_count,
            indexed_vectors=(
                indexing_summary.transcript_vectors
                + indexing_summary.visual_vectors
                + indexing_summary.caption_vectors
                if indexing_summary is not None
                else None
            ),
            frame_interval_seconds=frame_interval_seconds,
        )
        self.videos_table.put_item(
            Item={
                "video_id": message.video_id,
                "youtube_url": message.youtube_url,
                "title": metadata.title,
                "author": metadata.author,
                "duration_seconds": metadata.duration_seconds,
                "thumbnail_url": metadata.thumbnail_url,
                "artifact_stats": artifact_stats.model_dump(),
                "artifact_prefix": f"videos/{message.video_id}",
                "status": "ingested",
                "created_at": now,
                "updated_at": now,
            }
        )

    def _refresh_corpus_bm25_stats(self) -> None:
        """Rebuild corpus-wide BM25 stats by merging the per-video stats files.

        Per-video stats are small JSON (term -> df, plus avgdl/n_docs) and merge
        exactly into the whole-corpus fit, so this avoids re-downloading and
        re-tokenizing every transcript on every ingest (which made library
        growth quadratic). Merging from all per-video files (rather than
        incrementally updating the corpus file) keeps the refresh idempotent
        under SQS redelivery. If this fails, the just-ingested video remains
        valid because its per-video hybrid stats were already written.
        """
        try:
            stats = list(self._iter_bm25_stats())
            merged = BM25Encoder.merge_stats(stats)
            if not merged["n_docs"]:
                logger.warning("worker_corpus_bm25_skipped reason=no_video_stats")
                return
            self._upload_json(corpus_bm25_stats_key(), json.dumps(merged))
            logger.info(
                "worker_corpus_bm25_refreshed videos=%s chunks=%s",
                len(stats),
                merged["n_docs"],
            )
        except Exception:
            logger.exception("worker_corpus_bm25_refresh_error")

    def _iter_bm25_stats(self) -> Iterator[dict[str, Any]]:
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix="videos/"):
            for obj in page.get("Contents", []):
                key = str(obj.get("Key", ""))
                if not key.endswith("/vectors/bm25_stats.json"):
                    continue
                response = self.s3.get_object(Bucket=self.bucket, Key=key)
                yield json.loads(response["Body"].read().decode("utf-8"))


def _model_list_json(models: list[Any]) -> str:
    return "[" + ",".join(model.model_dump_json() for model in models) + "]"
