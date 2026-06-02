# Evaluation Methodology

Phase 5 currently contains a seed evaluation over one indexed video:
`QkdBXUikRQc` (`Stop Dreaming and Start Doing | Self-Sabotage`).

This is a real, reproducible harness validation run. It is not yet the final
portfolio-quality 60-80 query evaluation.

## Command

```bash
uv run python eval/run_eval.py \
  --golden eval/golden/seed.jsonl \
  --output apps/web/src/data/eval-results.json \
  --retrieval-depth 10
```

## Dataset

- Golden file: `eval/golden/seed.jsonl`
- Query count: 15
- Query types: transcript, timestamp, visual, hybrid, no-answer
- Labels: hand-verified from the Phase 2 transcript artifact and inspected frame images

## Metrics

Deterministic metrics:

- Recall@5
- Recall@10
- MRR
- Timestamp@5s
- Timestamp@10s
- Modality accuracy
- No-answer confusion matrix
- No-answer precision, recall, and F1

RAGAS / LLM judge metrics were skipped for this seed evaluation and are not
reported as numbers.

## Results

Primary config: `dense` with `min_source_score=0.2`.

| Metric | Value |
|---|---:|
| Recall@5 | 1.0000 |
| Recall@10 | 1.0000 |
| MRR | 0.9583 |
| Timestamp@5s | 0.9167 |
| Timestamp@10s | 0.9167 |
| Modality accuracy | 0.8333 |
| No-answer precision | 1.0000 |
| No-answer recall | 0.6667 |
| No-answer F1 | 0.8000 |

No-answer confusion matrix for the primary config:

| | Count |
|---|---:|
| True refuse | 2 |
| Missed refuse | 1 |
| Over-refuse | 0 |
| True answer | 12 |

## Limitations

- Only one video is indexed, so these metrics validate the harness rather than
  final retrieval quality.
- The primary config missed `q014` (`Show me a whiteboard diagram`) because visual
  retrieval returned the nearest available frame instead of refusing.
- Sparse BM25, local reranking, query rewrite, and RAGAS are not part of this seed
  run yet.

## Next Evaluation Work

- Ingest and index more demo videos.
- Expand the golden set toward 60-80 queries.
- Add BM25 sparse transcript retrieval.
- Add reranking and query rewrite configs.
- Run RAGAS or an explicit Haiku judge pass on baseline and final configs only.
