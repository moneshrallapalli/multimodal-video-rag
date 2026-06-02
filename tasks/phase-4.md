# Phase 4 — LangGraph Query Pipeline — TODO

Replace the Phase 1 mocked public search with a real retrieval + grounded answer pipeline while
preserving the existing `/api/search` response contract and frontend structure.

Conventions: granular conventional commits, push frequently, no `Co-Authored-By` trailer.

## Tasks

- [ ] A. Share Bedrock/Pinecone service clients across worker, graph, and API
- [ ] B. Build graph-domain retrieval candidate/context models
- [ ] C. Implement deterministic query validation and intent classification
- [ ] D. Retrieve transcript and visual candidates from Pinecone
- [ ] E. Fuse candidates with RRF and apply the retrieval no-answer gate
- [ ] F. Generate grounded answers with Claude Haiku 4.5
- [ ] G. Map graph output to the existing `SearchResponse`
- [ ] H. Wire `/api/search` to the real graph with safe test/fallback behavior
- [ ] I. Tests, docs, and live query smoke-test notes

## Guardrails

- Keep the public `SearchRequest` / `SearchResponse` contract stable.
- Do not redesign the frontend in Phase 4.
- Do not add reranking/BM25/eval work here; those deepen later stages.
- Keep visual and transcript Pinecone queries separate, then fuse across modalities.
- Refuse weak/off-domain queries rather than guessing.
- Do not print or commit secrets.

