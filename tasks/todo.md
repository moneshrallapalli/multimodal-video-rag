# Tasks Index

The day-to-day plan lives in per-phase files. Use this as a jumping-off point.

## Phase plans
- `phase-2.md` — ingestion pipeline (S3 + SQS + Fargate worker) — DONE
- `phase-3.md` — embeddings + Pinecone indexing — DONE
- `phase-4.md` — LangGraph query pipeline — DONE
- `phase-5.md` — seed evaluation — DONE
- `phase-6.md` — deployment + observability — DONE
- `phase-7-cleanup.md` — pre-reveal cleanup (audit follow-ups) — DONE
- `phase-8-quality.md` — quality + cost plan (all 6 items DONE 2026-06-12;
  see the session log's scoreboard: no-answer F1 0.611→0.714, judge correct
  0.75→0.803, over-refusals 13→7).
- `phase-8-session-log.md` — **NEXT: start here** — running log of Phase 8
  sessions; ends with the scoreboard, the 7 remaining over-refusals with
  their diagnosed causes, and the next levers (retrieval depth/targeting for
  timestamp-anchored visual queries, then library expansion).

## Open GitHub issues
- [#1](https://github.com/moneshrallapalli/multimodal-video-rag/issues/1) — `eval`: add a
  `--configs` flag to `run_eval.py` so a single ablation arm can be re-run without
  sweeping all of `CONFIGS`. Includes deciding what a partial run does to
  `apps/web/src/data/eval-results.json`.

## Engineering rules of the road
- `lessons.md` — gotchas hit during the build, with the rule to avoid repeating
  them. Read this if anything stops working unexpectedly.

## Conventions
- Granular conventional commits, **no `Co-Authored-By` trailer**, push frequently.
- Before every Python commit: `uvx ruff check . && uvx ruff format --check . && uv run pytest -q`.
- Before every web commit: `pnpm --filter web lint && typecheck && build`.
- Plan files own a per-task checklist with the actual change, file paths, and
  verification step; tick boxes (`[ ]` → `[x]`) as items land.

## Status snapshot
- Phases 0-6 complete; both prod endpoints live and answering 200.
- Phase 7 cleanup is complete: BM25 hybrid retrieval, cross-encoder rerank,
  query rewrite ablation, deploy, and live smoke are done.
- All Python tests + web build green in CI.
