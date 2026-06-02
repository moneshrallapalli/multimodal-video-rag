# Phase 5 — Evaluation — TODO

Build a reproducible seed evaluation harness over the currently indexed video, then expand it once
more demo videos are ingested and indexed.

Conventions: granular conventional commits, push frequently, no `Co-Authored-By` trailer.

## Tasks

- [ ] A. Golden dataset schema and seed `jsonl`
- [ ] B. Deterministic retrieval/no-answer metrics
- [ ] C. Eval runner that calls the Phase 4 query pipeline
- [ ] D. Threshold/config comparison output
- [ ] E. Real committed eval JSON for the dashboard
- [ ] F. Dashboard reads real seed output, not placeholder numbers
- [ ] G. Evaluation docs after live eval smoke passes
- [ ] H. Full verification and final Phase 5 status update

## Guardrails

- Do not fake metrics.
- Treat the current result as a seed eval over one indexed video, not final portfolio quality.
- Do not redesign the frontend.
- Do not rewrite Phase 4 retrieval except for tiny config hooks needed by evaluation.
- Keep RAGAS/LLM-judge values absent or explicitly skipped unless actually run.
- Do not print or commit secrets.

