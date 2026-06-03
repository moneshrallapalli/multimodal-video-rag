"""Index Phase 2 artifacts into Pinecone."""

from __future__ import annotations

from typing import Any

from shared import settings
from shared.bm25 import BM25Encoder
from shared.embedding import BedrockEmbedder
from shared.indexing import chunk_transcript, frame_vector_id
from shared.pinecone_client import PineconeIndexClient
from shared.schemas import (
    FrameArtifact,
    IndexingSummary,
    SparseVector,
    TranscriptArtifact,
    TranscriptChunk,
    VectorRecord,
    VideoMetadataArtifact,
)

from .media import FrameFile


class VideoIndexer:
    def __init__(
        self,
        *,
        bucket: str,
        embedder: BedrockEmbedder,
        transcript_index: PineconeIndexClient,
        visual_index: PineconeIndexClient,
        transcript_chunk_seconds: int = 30,
        transcript_chunk_overlap_seconds: int = 6,
    ) -> None:
        self.bucket = bucket
        self.embedder = embedder
        self.transcript_index = transcript_index
        self.visual_index = visual_index
        self.transcript_chunk_seconds = transcript_chunk_seconds
        self.transcript_chunk_overlap_seconds = transcript_chunk_overlap_seconds

    @classmethod
    def from_settings(cls, *, bucket: str) -> VideoIndexer:
        return cls(
            bucket=bucket,
            embedder=BedrockEmbedder(),
            transcript_index=PineconeIndexClient.from_index_name(
                settings.pinecone_transcript_index,
                expected_dim=settings.embed_dim,
                expected_metric="dotproduct",
            ),
            visual_index=PineconeIndexClient.from_index_name(
                settings.pinecone_visual_index,
                expected_dim=settings.embed_dim,
                expected_metric="cosine",
            ),
            transcript_chunk_seconds=settings.transcript_chunk_seconds,
            transcript_chunk_overlap_seconds=settings.transcript_chunk_overlap_seconds,
        )

    def index_video(
        self,
        *,
        metadata: VideoMetadataArtifact,
        transcript: TranscriptArtifact,
        frames: list[FrameFile],
        frame_keys: list[str],
    ) -> IndexingSummary:
        transcript_records, bm25_stats = self._transcript_records(
            metadata=metadata, transcript=transcript
        )
        visual_records = self._visual_records(
            metadata=metadata, frames=frames, frame_keys=frame_keys
        )

        transcript_count = self.transcript_index.upsert(transcript_records)
        visual_count = self.visual_index.upsert(visual_records)
        return IndexingSummary(
            video_id=metadata.video_id,
            transcript_vectors=transcript_count,
            visual_vectors=visual_count,
            bm25_stats=bm25_stats,
        )

    def _transcript_records(
        self,
        *,
        metadata: VideoMetadataArtifact,
        transcript: TranscriptArtifact,
    ) -> tuple[list[VectorRecord], dict[str, Any]]:
        """Build dense+sparse transcript records and return the BM25 stats.

        BM25 is fit per-video for now (single-video idf semantics). With more
        than one indexed video, prefer refitting against the union corpus so
        cross-video queries score consistently — that change is corpus-wide
        bookkeeping, not a code change here.
        """
        chunks = chunk_transcript(
            transcript,
            target_seconds=self.transcript_chunk_seconds,
            overlap_seconds=self.transcript_chunk_overlap_seconds,
        )
        chunk_texts = [chunk.text for chunk in chunks]
        vectors = self.embedder.embed_texts(chunk_texts)
        encoder = BM25Encoder.fit(chunk_texts)
        records: list[VectorRecord] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            sparse = encoder.encode_document(chunk.text)
            sparse_vector = (
                SparseVector(indices=list(sparse["indices"]), values=list(sparse["values"]))
                if sparse["indices"]
                else None
            )
            records.append(
                VectorRecord(
                    id=chunk.chunk_id,
                    values=vector,
                    metadata=_compact_metadata(_transcript_metadata(metadata, chunk)),
                    sparse_values=sparse_vector,
                )
            )
        return records, encoder.to_dict()

    def _visual_records(
        self,
        *,
        metadata: VideoMetadataArtifact,
        frames: list[FrameFile],
        frame_keys: list[str],
    ) -> list[VectorRecord]:
        artifacts = [
            FrameArtifact(
                frame_id=frame_vector_id(metadata.video_id, index),
                video_id=metadata.video_id,
                timestamp_seconds=frame.timestamp_seconds,
                s3_key=key,
            )
            for index, (frame, key) in enumerate(zip(frames, frame_keys, strict=True), start=1)
        ]
        return [
            VectorRecord(
                id=artifact.frame_id,
                values=self.embedder.embed_image(frame.path),
                metadata=_compact_metadata(_visual_metadata(metadata, artifact, self.bucket)),
            )
            for frame, artifact in zip(frames, artifacts, strict=True)
        ]


def _transcript_metadata(
    metadata: VideoMetadataArtifact,
    chunk: TranscriptChunk,
) -> dict[str, str | int | float | bool | None]:
    return {
        "video_id": chunk.video_id,
        "chunk_id": chunk.chunk_id,
        "start_seconds": chunk.start_seconds,
        "end_seconds": chunk.end_seconds,
        "title": metadata.title,
        "text": chunk.text,
        "modality": "transcript",
    }


def _visual_metadata(
    metadata: VideoMetadataArtifact,
    artifact: FrameArtifact,
    bucket: str,
) -> dict[str, str | int | float | bool | None]:
    return {
        "video_id": artifact.video_id,
        "frame_id": artifact.frame_id,
        "timestamp_seconds": artifact.timestamp_seconds,
        "title": metadata.title,
        "modality": "visual",
        "s3_uri": f"s3://{bucket}/{artifact.s3_key}",
    }


def _compact_metadata(
    metadata: dict[str, str | int | float | bool | None],
) -> dict[str, str | int | float | bool]:
    return {key: value for key, value in metadata.items() if value is not None}
