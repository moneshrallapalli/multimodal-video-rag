# Phase 4 — LangGraph Query Pipeline — TODO

Replace the Phase 1 mocked public search with a real retrieval + grounded answer pipeline while
preserving the existing `/api/search` response contract and frontend structure.

Conventions: granular conventional commits, push frequently, no `Co-Authored-By` trailer.

## Tasks

- [x] A. Share Bedrock/Pinecone service clients across worker, graph, and API
- [x] B. Build graph-domain retrieval candidate/context models
- [x] C. Implement deterministic query validation and intent classification
- [x] D. Retrieve transcript and visual candidates from Pinecone
- [x] E. Fuse candidates with RRF and apply the retrieval no-answer gate
- [x] F. Generate grounded answers with Claude Haiku 4.5
- [x] G. Map graph output to the existing `SearchResponse`
- [x] H. Wire `/api/search` to the real graph with safe test/fallback behavior
- [x] I. Tests, docs, and live query smoke-test notes

## Guardrails

- Keep the public `SearchRequest` / `SearchResponse` contract stable.
- Do not redesign the frontend in Phase 4.
- Do not add reranking/BM25/eval work here; those deepen later stages.
- Keep visual and transcript Pinecone queries separate, then fuse across modalities.
- Refuse weak/off-domain queries rather than guessing.
- Do not print or commit secrets.

## Review

**Outcome:** Phase 4 core query pipeline is complete. Configured `/api/search` requests now run
through a real LangGraph pipeline over Pinecone retrieval and Bedrock answer generation while
preserving the Phase 1 `SearchResponse` contract.

**Implemented**
- Shared Bedrock/Pinecone clients reused by worker, graph, and API.
- LangGraph pipeline nodes:
  `validate_query -> classify_intent -> retrieve_transcript -> retrieve_visual -> fuse_results ->
  apply_retrieval_gate -> build_context -> generate_answer`.
- Deterministic intent routing for visual, transcript, hybrid, timestamp, summary, and no-answer
  cases.
- Transcript retrieval via Titan Text v2 query embeddings and the `transcript` Pinecone index.
- Visual retrieval via Titan Multimodal text embeddings and the `visual` Pinecone index.
- Reciprocal Rank Fusion across modality-specific result lists.
- Cheap retrieval gate plus explicit off-domain refusals.
- Claude Haiku 4.5 answer generation through Bedrock Converse for transcript/hybrid contexts.
- Visual-only answers are extractive from retrieval metadata, avoiding unsupported image-content
  claims from a text-only LLM context.
- `/api/search` uses the real graph when configured, with a mock fallback for unconfigured local
  development/tests and a safe refusal on graph errors.

**Live smoke test (2026-06-02):**
- `Where do they talk about self sabotage?` -> `intent=transcript`, `refused=false`, `3` results,
  answer cites around `0:49` and `1:14`.
- `Show me the speaker at a desk` -> `intent=visual`, `refused=false`, `2` visual results,
  strongest match around `2:00`.
- `What is today's weather?` -> `intent=no_answer`, `refused=true`, `0` results.

**Out of scope (later):** BM25 sparse hybrid retrieval, local reranking, query rewrite, threshold
tuning, RAGAS, ablation metrics, and the full evaluation dashboard data. Those land in Phase 5.
