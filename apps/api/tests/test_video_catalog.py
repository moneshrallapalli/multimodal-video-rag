"""Coverage for the public catalog backed by completed ingestion records."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from api import video_catalog
from api.main import app
from fastapi.testclient import TestClient
from shared import settings


class FakeVideosTable:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.scans: list[dict[str, Any]] = []

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        self.scans.append(kwargs)
        return {"Items": self.items}


class FakeDynamoResource:
    def __init__(self, table: FakeVideosTable) -> None:
        self.table = table

    def Table(self, name: str) -> FakeVideosTable:
        assert name == "videos"
        return self.table


def test_public_videos_includes_ingested_dynamo_records(monkeypatch):
    table = FakeVideosTable(
        [
            {
                "video_id": "NEWVIDEO123",
                "youtube_url": "https://youtu.be/NEWVIDEO123",
                "title": "Freshly Indexed Talk",
                "author": "Test Creator",
                "duration_seconds": Decimal("123"),
                "status": "ingested",
                "created_at": "2026-06-05T12:00:00+00:00",
                "artifact_stats": {
                    "transcript_segments": Decimal("10"),
                    "transcript_chunks": Decimal("4"),
                    "visual_frames": Decimal("3"),
                    "indexed_vectors": Decimal("7"),
                    "frame_interval_seconds": Decimal("30"),
                },
            }
        ]
    )
    monkeypatch.setattr(settings, "sqs_queue_url", "queue-url")
    monkeypatch.setattr(settings, "dynamodb_videos_table", "videos")
    monkeypatch.setattr(
        video_catalog.boto3,
        "resource",
        lambda service, region_name: FakeDynamoResource(table),
    )

    response = TestClient(app).get("/api/videos")

    assert response.status_code == 200
    data = response.json()
    assert data[0] == {
        "id": "NEWVIDEO123",
        "title": "Freshly Indexed Talk",
        "author": "Test Creator",
        "domain": None,
        "thumbnail_url": "https://i.ytimg.com/vi/NEWVIDEO123/hqdefault.jpg",
        "youtube_url": "https://youtu.be/NEWVIDEO123",
        "duration_seconds": 123,
        "indexed": True,
        "artifact_stats": {
            "transcript_segments": 10,
            "transcript_chunks": 4,
            "visual_frames": 3,
            "indexed_vectors": 7,
            "frame_interval_seconds": 30,
        },
    }
    assert any(video["id"] == "QkdBXUikRQc" for video in data)


def test_public_videos_uses_dynamo_record_over_duplicate_seed(monkeypatch):
    table = FakeVideosTable(
        [
            {
                "video_id": "QkdBXUikRQc",
                "youtube_url": "https://youtu.be/QkdBXUikRQc",
                "title": "Updated Title From Ingestion",
                "author": "Updated Author",
                "status": "ingested",
                "created_at": "2026-06-05T12:00:00+00:00",
            }
        ]
    )
    monkeypatch.setattr(settings, "sqs_queue_url", "queue-url")
    monkeypatch.setattr(settings, "dynamodb_videos_table", "videos")
    monkeypatch.setattr(
        video_catalog.boto3,
        "resource",
        lambda service, region_name: FakeDynamoResource(table),
    )

    data = TestClient(app).get("/api/videos").json()

    matching = [video for video in data if video["id"] == "QkdBXUikRQc"]
    assert len(matching) == 1
    assert matching[0]["title"] == "Updated Title From Ingestion"
