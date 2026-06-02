"""Video indexer tests."""

from __future__ import annotations

from pathlib import Path

from ingest.indexing import VideoIndexer
from ingest.media import FrameFile
from shared.schemas import TranscriptArtifact, TranscriptSegment, VideoMetadataArtifact


class FakeEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.images: list[Path] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.texts.extend(texts)
        return [[float(index), 0.0, 0.0] for index, _text in enumerate(texts, start=1)]

    def embed_image(self, path: Path) -> list[float]:
        self.images.append(path)
        return [0.0, float(len(self.images)), 0.0]


class FakeIndex:
    def __init__(self) -> None:
        self.records = []

    def upsert(self, records):
        self.records.extend(records)
        return len(records)


def test_video_indexer_upserts_transcript_and_visual_records(tmp_path):
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"fake")
    embedder = FakeEmbedder()
    transcript_index = FakeIndex()
    visual_index = FakeIndex()
    indexer = VideoIndexer(
        bucket="test-bucket",
        embedder=embedder,
        transcript_index=transcript_index,
        visual_index=visual_index,
        transcript_chunk_seconds=20,
        transcript_chunk_overlap_seconds=5,
    )

    summary = indexer.index_video(
        metadata=VideoMetadataArtifact(
            video_id="QkdBXUikRQc",
            youtube_url="https://youtu.be/QkdBXUikRQc",
            title="Test Talk",
        ),
        transcript=TranscriptArtifact(
            video_id="QkdBXUikRQc",
            segments=[
                TranscriptSegment(start_seconds=0, end_seconds=10, text="hello"),
                TranscriptSegment(start_seconds=10, end_seconds=20, text="world"),
            ],
        ),
        frames=[FrameFile(path=image, timestamp_seconds=12)],
        frame_keys=["videos/QkdBXUikRQc/frames/frame_000001.jpg"],
    )

    assert summary.video_id == "QkdBXUikRQc"
    assert summary.transcript_vectors == 1
    assert summary.visual_vectors == 1
    assert embedder.texts == ["hello world"]
    assert embedder.images == [image]

    transcript_record = transcript_index.records[0]
    assert transcript_record.id == "QkdBXUikRQc:transcript:000001"
    assert transcript_record.metadata["video_id"] == "QkdBXUikRQc"
    assert transcript_record.metadata["start_seconds"] == 0
    assert transcript_record.metadata["end_seconds"] == 20
    assert transcript_record.metadata["text"] == "hello world"
    assert transcript_record.metadata["modality"] == "transcript"

    visual_record = visual_index.records[0]
    assert visual_record.id == "QkdBXUikRQc:frame:000001"
    assert visual_record.metadata["timestamp_seconds"] == 12
    assert visual_record.metadata["modality"] == "visual"
    assert (
        visual_record.metadata["s3_uri"]
        == "s3://test-bucket/videos/QkdBXUikRQc/frames/frame_000001.jpg"
    )


def test_video_indexer_handles_empty_transcript_and_frames():
    transcript_index = FakeIndex()
    visual_index = FakeIndex()
    indexer = VideoIndexer(
        bucket="test-bucket",
        embedder=FakeEmbedder(),
        transcript_index=transcript_index,
        visual_index=visual_index,
    )

    summary = indexer.index_video(
        metadata=VideoMetadataArtifact(video_id="vid", youtube_url="https://youtu.be/12345678901"),
        transcript=TranscriptArtifact(video_id="vid", segments=[]),
        frames=[],
        frame_keys=[],
    )

    assert summary.transcript_vectors == 0
    assert summary.visual_vectors == 0
    assert transcript_index.records == []
    assert visual_index.records == []
