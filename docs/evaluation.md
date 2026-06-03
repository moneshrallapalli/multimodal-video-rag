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
| MRR | 0.9028 |
| Timestamp@5s | 0.8333 |
| Timestamp@10s | 0.8333 |
| Modality accuracy | 0.9167 |
| No-answer precision | 1.0000 |
| No-answer recall | 0.6667 |
| No-answer F1 | 0.8000 |

Real-seed ablation summary:

| Config | Min source | Hybrid BM25 | Rerank | Rewrite | Recall@5 | Recall@10 | MRR | Timestamp@5s | Timestamp@10s | Modality acc | No-answer F1 |
|---|---:|:---:|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| Dense only | 0.20 | No | No | No | 1.0000 | 1.0000 | 0.9028 | 0.8333 | 0.8333 | 0.9167 | 0.8000 |
| Dense + loose gate | 0.05 | No | No | No | 1.0000 | 1.0000 | 0.9028 | 0.8333 | 0.8333 | 0.9167 | 0.5000 |
| Dense + strict gate | 0.50 | No | No | No | 0.6667 | 0.6667 | 0.6111 | 0.5833 | 0.5833 | 0.6667 | 0.6000 |
| Hybrid BM25 | 0.20 | Yes | No | No | 1.0000 | 1.0000 | 0.9028 | 0.8333 | 0.8333 | 0.9167 | 0.8000 |
| Hybrid + rerank | 0.20 | Yes | Yes | No | 1.0000 | 1.0000 | 0.9583 | 0.9167 | 0.9167 | 0.9167 | 0.8000 |
| Hybrid + rewrite | 0.20 | Yes | No | Yes | 1.0000 | 1.0000 | 0.8958 | 0.8333 | 0.8333 | 0.9167 | 0.5000 |

Hybrid rows loaded BM25 stats from S3 (`bm25_loaded=true`). The seed video was
originally indexed before sparse transcript vectors existed, so the seed
transcript was backfilled from the existing S3 transcript artifact before this
run.

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
- Query rewrite is intentionally reported as an ablation, not a claimed
  improvement; on this tiny seed it reduced no-answer F1.
- RAGAS / LLM judge metrics are not part of this seed run yet.

## Next Evaluation Work

- Ingest and index more demo videos.
- Expand the golden set toward 60-80 queries.
- Run RAGAS or an explicit Haiku judge pass on baseline and final configs only.
