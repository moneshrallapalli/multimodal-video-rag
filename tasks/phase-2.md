# Phase 2 — Ingestion Pipeline — TODO

Turn the Phase 1 mocked admin ingestion flow into a real async pipeline while preserving the
existing public search, admin UI, and typed response contracts.

Conventions: granular conventional commits, push frequently, no `Co-Authored-By` trailer.

## Tasks

- [x] A. Shared ingestion contracts and helpers
- [x] B. Admin API writes jobs to DynamoDB and enqueues SQS messages
- [x] C. Worker consumes SQS jobs and updates DynamoDB status
- [x] D. YouTube metadata/audio download and deterministic S3 artifact layout
- [x] E. Frame extraction artifacts
- [x] F. Transcript artifact path
- [x] G. Duplicate-job/idempotency behavior
- [x] H. Tests, docs, and local/AWS smoke-test notes

## Guardrails

- Preserve Phase 1 frontend routes, component structure, and API response shapes.
- Keep public search mocked until Phase 3/4 replaces retrieval and generation.
- Do not change or redeploy Phase 0 infrastructure unless a Phase 2 gap requires a scoped additive
  change.
- Do not print or commit secrets.

## Review

**Outcome:** Phase 2 core ingestion is complete. The admin API now writes deterministic YouTube
jobs to DynamoDB and enqueues SQS payloads; the worker drains SQS, downloads/processes the video,
writes S3 artifacts, records video metadata, and updates job status through completion/failure.

**Implemented**
- Shared internal contracts: `IngestJobMessage`, video metadata, frame artifacts, and transcript
  artifacts.
- Deterministic IDs and S3 keys: `yt_{youtube_id}` and `videos/{video_id}/...`.
- Admin API keeps Phase 1 routes/response shapes intact while switching to DynamoDB/SQS when
  `SQS_QUEUE_URL` is configured; tests force mock fallback.
- Duplicate ingest submissions return the existing DynamoDB job and do not enqueue again.
- Worker pipeline: SQS receive/delete semantics, status updates, `yt-dlp` metadata/download,
  ffmpeg audio/frame extraction, `faster-whisper` transcript artifact, S3 uploads, and video table
  record.
- Dockerfile updated for repo-root builds with `packages/shared`.

**Live smoke test (2026-06-02):**
- Queued `https://youtu.be/QkdBXUikRQc` through the real API store.
- Ran local worker against deployed SQS/DynamoDB/S3 with `INGEST_MAX_FRAMES=2`,
  `INGEST_FRAME_INTERVAL_SECONDS=120`, `WHISPER_MODEL_SIZE=tiny.en`.
- Result: job `yt_QkdBXUikRQc` completed at 100%, video record status `ingested`, and S3 contains
  `audio/audio.m4a`, two frame JPGs, `frames/frames.json`, `source/metadata.json`, and
  `transcript/transcript.json`.

**Out of scope (later):** embeddings/Pinecone upsert (Phase 3), LangGraph query path (Phase 4),
ECS/Fargate deployment and dispatcher automation (Phase 6).
