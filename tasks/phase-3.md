# Phase 3 — Embeddings And Pinecone — TODO

Turn Phase 2 artifacts into searchable Pinecone records while preserving the Phase 1 UI/API shape
and the Phase 2 ingestion structure.

Conventions: granular conventional commits, push frequently, no `Co-Authored-By` trailer.

## Tasks

- [x] A. Shared indexing contracts and deterministic vector IDs
- [x] B. Transcript chunking with timestamp preservation
- [x] C. Bedrock Titan text + multimodal embedding clients
- [x] D. Pinecone upsert/query helpers
- [x] E. Worker indexes transcript chunks and visual frames after artifact creation
- [x] F. Existing-artifact indexing script for Phase 2 smoke artifacts
- [x] G. Retrieval smoke utility over Pinecone
- [x] H. Tests, docs, and live Pinecone smoke-test notes

## Guardrails

- Do not replace public search with Pinecone yet; LangGraph/query answering lands in Phase 4.
- Keep visual and transcript embeddings in separate Pinecone indexes even though both are 1024-dim.
- Use deterministic vector IDs so re-indexing upserts rather than duplicates.
- Do not print or commit secrets.

## Review

**Outcome:** Phase 3 core indexing is complete. Phase 2 artifacts can now be embedded with Bedrock
Titan and upserted into the separate Pinecone transcript and visual indexes with citation-ready
metadata.

**Implemented**
- Shared indexing contracts: transcript chunks, vector records, indexing summaries, and retrieval
  hits.
- Deterministic vector IDs:
  - transcript: `{video_id}:transcript:{chunk_index}`
  - visual: `{video_id}:frame:{frame_index}`
- Segment-aware transcript chunking with timestamp preservation and overlap.
- Bedrock embedding client:
  - Titan Text v2 for transcript chunks
  - Titan Multimodal G1 for visual frames and visual text queries
  - 1024-dim assertions for both modalities
- Pinecone HTTP helper for index lookup, upsert, and smoke queries.
- Worker integration: after transcription, jobs move to `embedding`, vectors are upserted, and
  `videos/{video_id}/vectors/indexing_summary.json` is written to S3.
- Smoke scripts:
  - `scripts/index_existing_video.py`
  - `scripts/query_vectors.py`

**Live smoke test (2026-06-02):**
- Indexed existing Phase 2 artifacts for `QkdBXUikRQc`.
- Result: `15` transcript vectors and `2` visual vectors upserted.
- Transcript query `self sabotage` returned timestamped chunks, top hit
  `QkdBXUikRQc:transcript:000004` at `74.72s-105s`.
- Visual query `speaker at a desk` returned frame hits with S3 URIs and timestamps `0s` and `120s`.

**Out of scope (later):** public search replacement, RRF fusion, reranking, no-answer gates, and
Bedrock answer generation. Those land in Phase 4.
