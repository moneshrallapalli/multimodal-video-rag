# Phase 3 — Embeddings And Pinecone — TODO

Turn Phase 2 artifacts into searchable Pinecone records while preserving the Phase 1 UI/API shape
and the Phase 2 ingestion structure.

Conventions: granular conventional commits, push frequently, no `Co-Authored-By` trailer.

## Tasks

- [ ] A. Shared indexing contracts and deterministic vector IDs
- [ ] B. Transcript chunking with timestamp preservation
- [ ] C. Bedrock Titan text + multimodal embedding clients
- [ ] D. Pinecone upsert/query helpers
- [ ] E. Worker indexes transcript chunks and visual frames after artifact creation
- [ ] F. Existing-artifact indexing script for Phase 2 smoke artifacts
- [ ] G. Retrieval smoke utility over Pinecone
- [ ] H. Tests, docs, and live Pinecone smoke-test notes

## Guardrails

- Do not replace public search with Pinecone yet; LangGraph/query answering lands in Phase 4.
- Keep visual and transcript embeddings in separate Pinecone indexes even though both are 1024-dim.
- Use deterministic vector IDs so re-indexing upserts rather than duplicates.
- Do not print or commit secrets.

