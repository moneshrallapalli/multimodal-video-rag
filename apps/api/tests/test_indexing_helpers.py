"""Pure Phase 3 indexing helper coverage."""

from __future__ import annotations

from shared.indexing import chunk_transcript, frame_vector_id, transcript_vector_id
from shared.schemas import TranscriptArtifact, TranscriptSegment


def test_vector_ids_are_deterministic():
    assert transcript_vector_id("QkdBXUikRQc", 7) == "QkdBXUikRQc:transcript:000007"
    assert frame_vector_id("QkdBXUikRQc", 3) == "QkdBXUikRQc:frame:000003"


def test_chunk_transcript_preserves_timestamps_and_overlap():
    transcript = TranscriptArtifact(
        video_id="QkdBXUikRQc",
        segments=[
            TranscriptSegment(start_seconds=0, end_seconds=10, text="first"),
            TranscriptSegment(start_seconds=10, end_seconds=20, text="second"),
            TranscriptSegment(start_seconds=20, end_seconds=30, text="third"),
            TranscriptSegment(start_seconds=30, end_seconds=40, text="fourth"),
        ],
    )

    chunks = chunk_transcript(transcript, target_seconds=20, overlap_seconds=5)

    assert [chunk.chunk_id for chunk in chunks] == [
        "QkdBXUikRQc:transcript:000001",
        "QkdBXUikRQc:transcript:000002",
        "QkdBXUikRQc:transcript:000003",
    ]
    assert chunks[0].start_seconds == 0
    assert chunks[0].end_seconds == 20
    assert chunks[0].text == "first second"
    assert chunks[1].start_seconds == 10
    assert chunks[1].end_seconds == 30
    assert chunks[1].text == "second third"
    assert chunks[2].start_seconds == 20
    assert chunks[2].end_seconds == 40
    assert chunks[2].text == "third fourth"


def test_chunk_transcript_ignores_empty_segments():
    transcript = TranscriptArtifact(
        video_id="QkdBXUikRQc",
        segments=[
            TranscriptSegment(start_seconds=0, end_seconds=3, text=" "),
            TranscriptSegment(start_seconds=3, end_seconds=6, text="hello"),
        ],
    )

    chunks = chunk_transcript(transcript)

    assert len(chunks) == 1
    assert chunks[0].text == "hello"
    assert chunks[0].start_seconds == 3
