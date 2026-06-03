# Evaluation Methodology

Expanded real evaluation across 3 indexed videos and 60 hand-labeled queries. This is a genuine regression harness — not a final benchmark, but the numbers are real and reproducible.

## Command

```bash
# Retrieval metrics only (fast, no Bedrock)
uv run python eval/run_eval.py \
  --golden eval/golden/expanded.jsonl \
  --output apps/web/src/data/eval-results.json \
  --retrieval-depth 10

# With LLM judge on best configs
uv run python eval/run_eval.py \
  --golden eval/golden/expanded.jsonl \
  --output apps/web/src/data/eval-results.json \
  --retrieval-depth 10 \
  --judge haiku \
  --judge-configs dense,production
```

## Dataset

- Golden file: `eval/golden/expanded.jsonl`
- Query count: 60
- Videos: 3 (QkdBXUikRQc, DVtcZQ2QdBg, as9IYFrTiKc)
- Query types: transcript, timestamp, visual, hybrid, summary, no-answer
- Labels: hand-verified from actual S3 transcript artifacts and frame contact sheets
- Includes 3 cross-video (unfiltered) queries to test corpus-wide retrieval

## Metrics

Deterministic retrieval metrics:
- Recall@5, Recall@10
- MRR (Mean Reciprocal Rank)
- Timestamp@5s (top result within 5s of ground truth)
- Timestamp@10s
- Modality accuracy
- No-answer precision, recall, F1

LLM judge (Haiku-scored on answerable queries only):
- Answer quality (0-1)
- Grounded rate (answer supported by retrieved evidence)
- Correct rate (matches reference answer)
- Useful rate (would help the user)

## Results

| Config | Recall@5 | Recall@10 | MRR | Timestamp@5s | Modality acc | No-answer F1 |
|---|---:|---:|---:|---:|---:|---:|
| Dense only | 0.9815 | 1.0000 | 0.9290 | 0.8889 | 0.9630 | 0.5000 |
| Dense + loose gate | 0.9815 | 1.0000 | 0.9290 | 0.8889 | 0.9630 | 0.2858 |
| Dense + strict gate | 0.7963 | 0.8148 | 0.7654 | 0.7407 | 0.7963 | 0.2222 |
| Hybrid BM25 | 1.0000 | 1.0000 | 0.9198 | 0.8704 | 0.9630 | 0.2858 |
| Hybrid + rerank | 1.0000 | 1.0000 | 0.9336 | 0.8889 | 0.9630 | 0.2858 |
| Hybrid + rewrite | 1.0000 | 1.0000 | 0.9198 | 0.8704 | 0.9630 | 0.2858 |
| **Production** | **1.0000** | **1.0000** | **0.9336** | **0.8889** | **0.9630** | **0.2858** |

LLM judge on answerable queries (n=54 per config):

| Config | Quality | Grounded | Correct | Useful |
|---|---:|---:|---:|---:|
| Dense | 0.747 | 0.815 | 0.667 | 0.741 |
| **Production** | **0.753** | **0.815** | **0.704** | **0.741** |

Production is the deployed config: Hybrid BM25 + cross-encoder rerank + query rewrite.

## No-answer analysis

6 no-answer queries total. Production correctly refuses 1 (off-domain keyword match: "weather").
The 5 missed refusals are all in-domain, content-absent queries — the topic doesn't exist in
the video but the dense score stays above 0.2 because the video has adjacent content.

| Query | Why it slips through |
|---|---|
| "salary negotiation?" → self-sabotage video | Planning section scores ~0.39 |
| "whiteboard diagram?" → self-sabotage video | Nearest visual frame scores ~0.39 |
| "sprint review time boxes?" → finance video | Finance planning content scores ~0.36 |
| "anti-vision boards?" → sprint review video | Sprint review content scores ~0.38 |
| "garden tutorial?" → sprint review video | Nearest visual frame scores ~0.39 |

Raising the dense threshold would fix some of these but would cut recall on answerable queries
that score in the same range. Fixing this properly requires semantic "is this topic present?"
reasoning, not just a threshold.

## Limitations

- 3 videos is enough to validate the harness across modalities, not enough for final benchmark claims.
- No-answer F1 is the main weakness (5 in-domain content-absent misses).
- RAGAS metrics not yet run.
