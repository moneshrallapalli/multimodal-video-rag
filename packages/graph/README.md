# graph

The LangGraph query pipeline: query validation, intent classification, query
rewrite, visual + transcript retrieval, Reciprocal Rank Fusion, reranking,
context building, Bedrock generation, and two-gate grounding (refuse when
evidence is weak). `state.py` defines the typed state threaded through it.

Phase 4 core is implemented:

```text
validate_query
-> classify_intent
-> retrieve_transcript / retrieve_visual
-> fuse_results (RRF)
-> apply_retrieval_gate
-> build_context
-> generate_answer
```

BM25 sparse retrieval, reranking, query rewrite, and threshold tuning are Phase 5+ work.
