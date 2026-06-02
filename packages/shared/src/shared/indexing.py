"""Pure helpers for Phase 3 indexing.

Concrete Bedrock and Pinecone clients live in the worker package. These helpers
stay dependency-light so API, worker, tests, and later retrieval code can share
the same chunking and vector-id rules.
"""

from __future__ import annotations

from shared.schemas import TranscriptArtifact, TranscriptChunk, TranscriptSegment


def transcript_vector_id(video_id: str, chunk_index: int) -> str:
    return f"{video_id}:transcript:{chunk_index:06d}"


def frame_vector_id(video_id: str, frame_index: int) -> str:
    return f"{video_id}:frame:{frame_index:06d}"


def chunk_transcript(
    transcript: TranscriptArtifact,
    *,
    target_seconds: int = 30,
    overlap_seconds: int = 6,
) -> list[TranscriptChunk]:
    """Group transcript segments into timestamp-preserving chunks.

    The worker's faster-whisper output is already segment-aware. This keeps
    segment boundaries intact and advances by a small overlap so boundary facts
    are still retrievable from adjacent chunks.
    """
    segments = [
        segment
        for segment in sorted(transcript.segments, key=lambda s: (s.start_seconds, s.end_seconds))
        if segment.text.strip()
    ]
    if not segments:
        return []

    chunks: list[TranscriptChunk] = []
    start_index = 0
    while start_index < len(segments):
        window = _window_from(segments, start_index, target_seconds)
        chunk_index = len(chunks) + 1
        text = " ".join(segment.text.strip() for segment in window)
        chunks.append(
            TranscriptChunk(
                chunk_id=transcript_vector_id(transcript.video_id, chunk_index),
                video_id=transcript.video_id,
                start_seconds=window[0].start_seconds,
                end_seconds=window[-1].end_seconds,
                text=text,
            )
        )

        if start_index + len(window) >= len(segments):
            break
        next_start = _next_start_index(
            segments,
            start_index=start_index,
            chunk_end=window[-1].end_seconds,
            overlap_seconds=overlap_seconds,
        )
        start_index = max(start_index + 1, next_start)

    return chunks


def _window_from(
    segments: list[TranscriptSegment],
    start_index: int,
    target_seconds: int,
) -> list[TranscriptSegment]:
    start_time = segments[start_index].start_seconds
    end_index = start_index
    while end_index + 1 < len(segments):
        current = segments[end_index]
        if current.end_seconds - start_time >= target_seconds:
            break
        end_index += 1
    return segments[start_index : end_index + 1]


def _next_start_index(
    segments: list[TranscriptSegment],
    *,
    start_index: int,
    chunk_end: float,
    overlap_seconds: int,
) -> int:
    threshold = max(0.0, chunk_end - overlap_seconds)
    for index in range(start_index, len(segments)):
        if segments[index].end_seconds > threshold:
            return index
    return start_index + 1
