"""Generate eval golden dataset from actual S3 transcript and caption artifacts.

Downloads transcript.json and captions.json for each ingested video, then uses
Bedrock Claude to generate diverse golden queries with verified timestamps.

Usage:
    uv run python scripts/generate_golden.py                     # generate both seed + expanded
    uv run python scripts/generate_golden.py --seed-only         # just seed (1 video, fast)
    uv run python scripts/generate_golden.py --dump-transcripts  # dump transcripts for review
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "shared" / "src"))

from shared import settings  # noqa: E402

SEED_VIDEO = "QkdBXUikRQc"

VIDEOS = [
    "QkdBXUikRQc",
    "DVtcZQ2QdBg",
    "as9IYFrTiKc",
    "u4ZoJKF_VuA",
    "1Gdl-A1DvpA",
    "iCvmsMzlF7o",
    "TGdLss5Srnk",
    "E76CUtSHMrU",
    "h6fcK_fRYaI",
    "v7AYKMP6rOE",
    "Th8JoIan4dg",
    "arj7oStGLkU",
    "uxPdPpi5W4o",
]

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "eval" / "golden"

PROMPT_TEMPLATE = """\
You are generating evaluation queries for a video search engine. Given a video's
transcript (with exact timestamps from Whisper) and frame captions, generate
golden test queries.

VIDEO_ID: {video_id}
TITLE: {title}

TRANSCRIPT (each segment has start_seconds and end_seconds):
{transcript_text}

FRAME CAPTIONS (each has timestamp_seconds):
{captions_text}

Generate exactly {n_queries} queries as a JSON array. Each query must be one of:
- "transcript": questions about what was SAID (use transcript timestamps)
- "visual": questions about what was SHOWN on screen (use frame timestamps)
- "hybrid": questions requiring both visual and spoken content
- "timestamp": questions asking WHEN something happened (use transcript timestamps)
- "no_answer": questions about topics NOT in the video (relevant_timestamps=[], reference_answer=null)

Distribution: ~50% transcript, ~15% visual, ~10% hybrid, ~10% timestamp, ~15% no_answer.

CRITICAL RULES:
1. relevant_timestamps MUST be exact [start_seconds, end_seconds] from the transcript segments or frame captions provided above. Do NOT estimate or round.
2. reference_answer must accurately describe what is actually said/shown at those timestamps.
3. For visual queries, use the frame timestamp as both start and end: [timestamp, timestamp].
4. For no_answer queries: relevant_timestamps=[], expected_modality="none", reference_answer=null.
5. Queries should be natural questions a real user would ask.

Output format (JSON array, no markdown):
[
  {{
    "query": "What does the speaker say about X?",
    "type": "transcript",
    "relevant_timestamps": [[start, end]],
    "expected_modality": "transcript",
    "reference_answer": "The speaker explains that...",
    "notes": "From transcript segment at M:SS-M:SS"
  }}
]
"""

CROSS_CORPUS_PROMPT = """\
Generate {n} cross-corpus evaluation queries that span multiple videos. These test
whether the system can identify the RIGHT video when no video_id filter is provided.

Available videos and their topics:
{video_summaries}

For each query:
- Set video_id to null (the system must find the right video)
- Set expected_video_id to the video that should be retrieved
- Use actual timestamps from that video's transcript
- Types should be "transcript" or "summary"

Output format (JSON array, no markdown):
[
  {{
    "query": "Which video discusses X?",
    "type": "transcript",
    "video_id": null,
    "expected_video_id": "VIDEO_ID",
    "relevant_timestamps": [[start, end]],
    "expected_modality": "transcript",
    "reference_answer": "In the video about Y, the speaker says...",
    "notes": "Cross-corpus query targeting VIDEO_ID"
  }}
]
"""


def _download_json(s3, bucket: str, key: str) -> dict | list | None:
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read().decode())
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as exc:
        print(f"  WARN: failed to download {key}: {exc}")
        return None


def _load_video_artifacts(s3, bucket: str, video_id: str) -> dict | None:
    transcript = _download_json(s3, bucket, f"videos/{video_id}/transcript/transcript.json")
    if not transcript:
        print(f"  SKIP {video_id} (no transcript artifact)")
        return None

    captions = _download_json(s3, bucket, f"videos/{video_id}/frames/captions.json") or []
    metadata = _download_json(s3, bucket, f"videos/{video_id}/source/metadata.json") or {}
    frames = _download_json(s3, bucket, f"videos/{video_id}/frames/frames.json") or []

    return {
        "video_id": video_id,
        "title": metadata.get("title", video_id),
        "transcript": transcript,
        "captions": captions,
        "frames": frames,
    }


def _format_transcript(transcript: dict) -> str:
    segments = transcript.get("segments", [])
    lines = []
    for seg in segments:
        start = seg["start_seconds"]
        end = seg["end_seconds"]
        text = seg["text"]
        m1, s1 = divmod(int(start), 60)
        m2, s2 = divmod(int(end), 60)
        lines.append(f"[{start:.2f}-{end:.2f}] ({m1}:{s1:02d}-{m2}:{s2:02d}) {text}")
    return "\n".join(lines)


def _format_captions(captions: list, frames: list) -> str:
    if not captions:
        return "(no captions available)"
    lines = []
    for i, caption in enumerate(captions):
        ts = 0.0
        if i < len(frames):
            ts = frames[i].get("timestamp_seconds", 0.0)
        m, s = divmod(int(ts), 60)
        lines.append(f"[{ts:.1f}s] ({m}:{s:02d}) {caption}")
    return "\n".join(lines)


def _call_bedrock(prompt: str) -> str:
    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    response = client.converse(
        modelId=settings.bedrock_llm_model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 8192, "temperature": 0.3},
    )
    text = response["output"]["message"]["content"][0]["text"]
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return text


def _generate_queries_for_video(
    artifacts: dict, n_queries: int, id_prefix: str, start_id: int
) -> list[dict]:
    prompt = PROMPT_TEMPLATE.format(
        video_id=artifacts["video_id"],
        title=artifacts["title"],
        transcript_text=_format_transcript(artifacts["transcript"]),
        captions_text=_format_captions(artifacts["captions"], artifacts["frames"]),
        n_queries=n_queries,
    )

    raw = _call_bedrock(prompt)
    queries = json.loads(raw)

    result = []
    for i, q in enumerate(queries):
        entry = {
            "id": f"{id_prefix}{start_id + i:03d}",
            "query": q["query"],
            "type": q["type"],
            "video_id": artifacts["video_id"],
            "relevant_timestamps": q.get("relevant_timestamps", []),
            "expected_modality": q.get("expected_modality", "transcript"),
            "reference_answer": q.get("reference_answer"),
            "notes": q.get("notes", ""),
        }
        if q["type"] == "no_answer":
            entry["relevant_timestamps"] = []
            entry["expected_modality"] = "none"
            entry["reference_answer"] = None
        result.append(entry)
    return result


def _generate_cross_corpus(all_artifacts: list[dict], start_id: int) -> list[dict]:
    summaries = []
    for a in all_artifacts:
        segs = a["transcript"].get("segments", [])
        preview = " ".join(s["text"] for s in segs[:10])
        summaries.append(f"- {a['video_id']}: \"{a['title']}\" — {preview[:200]}...")

    prompt = CROSS_CORPUS_PROMPT.format(
        n=5,
        video_summaries="\n".join(summaries),
    )

    raw = _call_bedrock(prompt)
    queries = json.loads(raw)

    result = []
    for i, q in enumerate(queries):
        result.append({
            "id": f"e{start_id + i:03d}",
            "query": q["query"],
            "type": q.get("type", "transcript"),
            "video_id": None,
            "expected_video_id": q.get("expected_video_id"),
            "relevant_timestamps": q.get("relevant_timestamps", []),
            "expected_modality": q.get("expected_modality", "transcript"),
            "reference_answer": q.get("reference_answer"),
            "notes": q.get("notes", "Cross-corpus query"),
        })
    return result


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(entries)} queries to {path}")


def dump_transcripts() -> None:
    s3 = boto3.client("s3", region_name=settings.aws_region)
    bucket = settings.s3_bucket
    if not bucket:
        print("ERROR: S3_BUCKET not set", file=sys.stderr)
        sys.exit(1)

    out_dir = Path("eval/transcripts")
    out_dir.mkdir(parents=True, exist_ok=True)

    for video_id in VIDEOS:
        artifacts = _load_video_artifacts(s3, bucket, video_id)
        if not artifacts:
            continue
        out = out_dir / f"{video_id}.txt"
        with open(out, "w") as f:
            f.write(f"TITLE: {artifacts['title']}\n")
            f.write(f"VIDEO_ID: {video_id}\n\n")
            f.write("=== TRANSCRIPT ===\n")
            f.write(_format_transcript(artifacts["transcript"]))
            f.write("\n\n=== FRAME CAPTIONS ===\n")
            f.write(_format_captions(artifacts["captions"], artifacts["frames"]))
        print(f"  Dumped {video_id} -> {out}")

    print(f"\nTranscripts saved to {out_dir}/")
    print("Review them, then run without --dump-transcripts to generate golden queries.")


def main() -> None:
    if "--dump-transcripts" in sys.argv:
        dump_transcripts()
        return

    s3 = boto3.client("s3", region_name=settings.aws_region)
    bucket = settings.s3_bucket
    if not bucket:
        print("ERROR: S3_BUCKET not set", file=sys.stderr)
        sys.exit(1)

    seed_only = "--seed-only" in sys.argv

    print("Loading video artifacts from S3...\n")
    all_artifacts = []
    for video_id in VIDEOS:
        artifacts = _load_video_artifacts(s3, bucket, video_id)
        if artifacts:
            all_artifacts.append(artifacts)
            print(f"  Loaded {video_id}: {len(artifacts['transcript'].get('segments', []))} segments, {len(artifacts['captions'])} captions")

    if not all_artifacts:
        print("ERROR: no video artifacts found in S3. Ingest videos first.", file=sys.stderr)
        sys.exit(1)

    # --- Seed: 15 queries from the seed video ---
    print("\nGenerating seed queries...")
    seed_artifacts = next((a for a in all_artifacts if a["video_id"] == SEED_VIDEO), None)
    if not seed_artifacts:
        print(f"ERROR: seed video {SEED_VIDEO} not found in S3", file=sys.stderr)
        sys.exit(1)

    seed_queries = _generate_queries_for_video(seed_artifacts, 15, "q", 1)
    _write_jsonl(GOLDEN_DIR / "seed.jsonl", seed_queries)

    if seed_only:
        print("\nDone (seed only).")
        return

    # --- Expanded: ~10 per video + cross-corpus ---
    print("\nGenerating expanded queries...")
    expanded_queries = []
    query_id = 1
    for artifacts in all_artifacts:
        print(f"  Generating for {artifacts['video_id']}...")
        queries = _generate_queries_for_video(artifacts, 10, "e", query_id)
        expanded_queries.extend(queries)
        query_id += len(queries)

    print("  Generating cross-corpus queries...")
    cross = _generate_cross_corpus(all_artifacts, query_id)
    expanded_queries.extend(cross)

    _write_jsonl(GOLDEN_DIR / "expanded.jsonl", expanded_queries)

    print(f"\nDone. Generated {len(seed_queries)} seed + {len(expanded_queries)} expanded queries.")
    print("Verify with: uv run pytest eval/tests/test_golden_seed.py -v")


if __name__ == "__main__":
    main()
