# eval

Offline evaluation harness. Holds hand-verified golden datasets, deterministic
retrieval/no-answer metrics, and the runner that writes the dashboard JSON.

## Seed Eval

The current seed set evaluates the single indexed video `QkdBXUikRQc`.

```bash
uv run python eval/run_eval.py \
  --golden eval/golden/seed.jsonl \
  --output apps/web/src/data/eval-results.json \
  --retrieval-depth 10
```

The output is committed at `apps/web/src/data/eval-results.json` and rendered by
the `/eval` dashboard.

## Current Scope

Implemented:

- golden JSONL schema
- deterministic Recall@5 / Recall@10
- MRR
- Timestamp@5s / Timestamp@10s
- modality accuracy
- no-answer confusion matrix, precision, recall, and F1
- dense retrieval gate comparison
- BM25 sparse transcript retrieval ablation
- cross-encoder rerank ablation
- query rewrite ablation

Skipped in the seed run:

- RAGAS / LLM judge metrics
- expanded multi-video benchmark

The current dashboard output includes six configs: dense, dense loose gate, dense
strict gate, hybrid BM25, hybrid + rerank, and hybrid + rewrite. The remaining
eval gap is scale: more videos, more hand-labeled queries, and optional judge
metrics once the deterministic benchmark is larger.
