"""Public video catalog assembled from persisted ingestion records."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import boto3
from shared import settings
from shared.schemas import DemoVideo, VideoArtifactStats

from .mock_data import DEMO_VIDEOS

logger = logging.getLogger("video_rag.api.catalog")

_MAX_CATALOG_ITEMS = 200
_INDEXED_STATUSES = {"completed", "indexed", "ingested"}


class DynamoVideoCatalog:
    """Read the public video catalog from the ingestion videos table."""

    def __init__(self, *, videos_table: Any) -> None:
        self._videos_table = videos_table

    def list_videos(self) -> list[DemoVideo]:
        items = self._scan_items()
        items.sort(
            key=lambda item: str(item.get("created_at") or item.get("updated_at") or ""),
            reverse=True,
        )
        videos: list[DemoVideo] = []
        for item in items:
            video = _item_to_video(item)
            if video:
                videos.append(video)
        return videos

    def _scan_items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        start_key: dict[str, Any] | None = None
        while len(items) < _MAX_CATALOG_ITEMS:
            limit = min(100, _MAX_CATALOG_ITEMS - len(items))
            kwargs: dict[str, Any] = {"Limit": limit}
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            response = self._videos_table.scan(**kwargs)
            items.extend(response.get("Items", []))
            start_key = response.get("LastEvaluatedKey")
            if not start_key:
                break
        return items[:_MAX_CATALOG_ITEMS]


def list_public_videos() -> list[DemoVideo]:
    """Return dynamic ingested videos plus the curated seed catalog.

    Local/test environments without SQS configured keep using the deterministic
    seed list. Deployed environments read DynamoDB records written by the worker
    and merge them ahead of the seeds so newly completed ingestions show up on
    the home screen and in the video filter.
    """
    if not real_catalog_enabled():
        return DEMO_VIDEOS
    try:
        dynamic = _dynamo_catalog().list_videos()
    except Exception:
        logger.exception("video_catalog_read_error")
        return DEMO_VIDEOS
    if not dynamic:
        return DEMO_VIDEOS
    return _merge_with_seed_catalog(dynamic)


def real_catalog_enabled() -> bool:
    return bool(settings.sqs_queue_url and settings.dynamodb_videos_table)


def _dynamo_catalog() -> DynamoVideoCatalog:
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    return DynamoVideoCatalog(videos_table=dynamodb.Table(settings.dynamodb_videos_table))


def _merge_with_seed_catalog(dynamic: list[DemoVideo]) -> list[DemoVideo]:
    merged: list[DemoVideo] = []
    seen: set[str] = set()
    for video in [*dynamic, *DEMO_VIDEOS]:
        if video.id in seen:
            continue
        merged.append(video)
        seen.add(video.id)
    return merged


def _item_to_video(item: dict[str, Any]) -> DemoVideo | None:
    video_id = str(item.get("video_id") or item.get("id") or "")
    if not video_id:
        logger.warning("video_catalog_skipped_item reason=missing_video_id")
        return None
    return DemoVideo(
        id=video_id,
        title=str(item.get("title") or "Indexed video"),
        author=str(item.get("author") or "Unknown"),
        domain=item.get("domain"),
        thumbnail_url=str(item.get("thumbnail_url") or _thumb(video_id)),
        youtube_url=str(item.get("youtube_url") or _watch(video_id)),
        duration_seconds=_coerce_optional_int(item.get("duration_seconds")),
        indexed=str(item.get("status") or "ingested") in _INDEXED_STATUSES,
        artifact_stats=_artifact_stats(item.get("artifact_stats")),
    )


def _artifact_stats(value: Any) -> VideoArtifactStats | None:
    if not isinstance(value, dict):
        return None
    return VideoArtifactStats(
        transcript_segments=_coerce_optional_int(value.get("transcript_segments")),
        transcript_chunks=_coerce_optional_int(value.get("transcript_chunks")),
        visual_frames=_coerce_optional_int(value.get("visual_frames")),
        indexed_vectors=_coerce_optional_int(value.get("indexed_vectors")),
        frame_interval_seconds=_coerce_optional_int(value.get("frame_interval_seconds")),
    )


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _thumb(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _watch(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"
