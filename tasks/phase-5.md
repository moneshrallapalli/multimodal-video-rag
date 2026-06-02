# Phase 5 — Evaluation — TODO

Build a reproducible seed evaluation harness over the currently indexed video, then expand it once
more demo videos are ingested and indexed.

Conventions: granular conventional commits, push frequently, no `Co-Authored-By` trailer.

## Tasks

- [x] A. Golden dataset schema and seed `jsonl`
- [x] B. Deterministic retrieval/no-answer metrics
- [x] C. Eval runner that calls the Phase 4 query pipeline
- [x] D. Threshold/config comparison output
- [x] E. Real committed eval JSON for the dashboard
- [x] F. Dashboard reads real seed output, not placeholder numbers
- [x] G. Evaluation docs after live eval smoke passes
- [x] H. Full verification and final Phase 5 status update

## Guardrails

- Do not fake metrics.
- Treat the current result as a seed eval over one indexed video, not final portfolio quality.
- Do not redesign the frontend.
- Do not rewrite Phase 4 retrieval except for tiny config hooks needed by evaluation.
- Keep RAGAS/LLM-judge values absent or explicitly skipped unless actually run.
- Do not print or commit secrets.

## Review

**Outcome:** Phase 5 seed evaluation is complete. The repo now has a hand-labeled seed golden set,
a reproducible eval runner, deterministic retrieval/no-answer metrics, and a committed real eval
JSON artifact rendered by the dashboard.

**Seed scope**
- Dataset: `15` queries over currently indexed video `QkdBXUikRQc`.
- Composition: transcript, timestamp, visual, hybrid, and no-answer cases.
- RAGAS/LLM-judge metrics: intentionally skipped for this seed run; no fake judge numbers.

**Live eval smoke (2026-06-02)**
- Command:
  `uv run python eval/run_eval.py --golden eval/golden/seed.jsonl --output apps/web/src/data/eval-results.json --retrieval-depth 10`
- Primary config: `dense` (`min_source_score=0.2`).
- Primary metrics:
  - Recall@5: `1.0000`
  - Recall@10: `1.0000`
  - MRR: `0.9583`
  - Timestamp@5s: `0.9167`
  - Timestamp@10s: `0.9167`
  - Modality accuracy: `0.8333`
  - No-answer precision: `1.0000`
  - No-answer recall: `0.6667`
  - No-answer F1: `0.8000`

**Notable limitation**
- The primary config missed `q014` (`Show me a whiteboard diagram`) because visual retrieval returns
  the closest available frame instead of refusing. This is a useful threshold/grounding target for
  the next evaluation pass.

