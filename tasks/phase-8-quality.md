# Phase 8 — retrieval/answer quality + cost-aware pipeline cleanup

Handoff written 2026-06-11 at the end of the motion + gate-collapse session.
Read this first in the next session: it records what landed, what went wrong,
the current real numbers, and the concrete plan to improve them.

## What landed this session (all pushed, `ec1ebad..b3911f2`)

- **UI motion pass** (5 commits): `motion` library + easing tokens +
  reduced-motion guard (`apps/web/src/lib/motion.ts`, `motion-provider.tsx`);
  search → answer reveal choreography (skeleton mirror, staggered proofs,
  `layoutId` active-proof ring); admin status-badge crossfades + smooth
  progress; eval count-ups + sliding config pill. `PRODUCT.md` records the
  design register and motion principles.
- **Gate collapse** (`55f8c9c`): deleted the `_OFF_DOMAIN` keyword blocklist
  and `_LLM_REFUSAL_PHRASES` substring matching. The answer call now returns
  structured JSON `{"answer", "grounded"}` (`packages/graph/src/graph/
  answering.py`, `GeneratedAnswer`); the pipeline refuses on `grounded=false`
  (`pipeline.py::_generate_answer`). Parser tolerates fences/prose and logs
  `answer_parse_fallback` on drift (0 fallbacks in 270+ real calls).
- **Eval artifact regenerated** (`b3911f2`) on the *current* golden set with
  Haiku judge on production.

## What went wrong (and the trap for next time)

The committed `apps/web/src/data/eval-results.json` was **stale**: the golden
set was rebuilt on Jun 6 (145 → 135 queries, commit `9f9dc23`) but the eval
was never re-run, so the dashboard still showed Jun 3 numbers. The first
post-change eval run looked like a catastrophic regression across configs
whose code had not changed. Diagnosis: impossible drops in untouched configs
⇒ environment drift, not code. Fix: re-ran the OLD code on the CURRENT golden
set (scoped to one config by monkeypatching `run_eval.CONFIGS` — ~5 min) for
a clean A/B. **Rule: never compare against the committed artifact without
checking `meta.generated_at` vs `git log -- eval/golden/`.** (Also recorded in
`lessons.md` and auto-memory.)

## Current real numbers (135-query golden set, 13 indexed videos)

Production config (hybrid + rerank + rewrite + answer gen):

| metric | old (phrase-sniff) | new (grounded flag) |
|---|---|---|
| no-answer F1 | 0.600 | **0.611** |
| no-answer precision | 0.429 | **0.458** (13 over-refusals) |
| no-answer recall | 1.000 | 0.917 (1 missed refusal) |
| MRR | 0.774 | **0.791** |
| Timestamp@5s | 0.732 | **0.740** |

Judge (production, n=110): quality 0.85, grounded 0.94, correct 0.75, useful 0.94.

Retrieval-only configs sit at MRR 0.68–0.76 — lower than the old dashboard
showed because the rebuilt golden set is harder, not because of any code
change (verified: the keyword gate fired on zero current no-answer cases).

## How to improve the scores — prioritized

1. **Over-refusal tuning (biggest no-answer F1 lever).** 13 answerable
   queries are wrongly refused (precision 0.458). Determine which layer
   refuses each: per-modality dense gate
   (`pipeline.py::_apply_retrieval_gate`, thresholds in `models.py`:
   `min_transcript_source_score=0.2`, `min_visual_source_score=0.4`) vs LLM
   `grounded=false` (prompt in `answering.py::_prompt`). Add per-query refusal
   provenance to the eval run, then either soften the prompt's grounding
   criteria or lower thresholds. Target precision ≥0.6 while keeping recall
   ≥0.9. A session chip for this already exists ("Tune production no-answer
   over-refusals").
2. **The 1 missed refusal**: find it in the per-query records; likely the LLM
   answered confidently from weak context. Cheap prompt nudge once identified.
3. **Correct_rate 0.75 (judge)**: ~27 answers judged incorrect. Inspect the
   judged transcripts — common causes are wrong-timestamp citations and
   summary-style queries answered from a single chunk. May motivate larger
   `retrieve_top_k` for summary intent.
4. **Rewrite-on-miss + parallel retrieval** (from the cost top-3): run
   retrieval with the raw query first; only rewrite + retry when the gate
   refuses or top score is weak. Also fan out `retrieve_transcript` /
   `retrieve_visual` in parallel in the LangGraph graph (independent nodes,
   currently serial edges in `pipeline.py::_build_graph`). ~50% fewer LLM
   calls per query, faster p50, and a fresh ablation row for the dashboard.
5. **Scene-detection frame sampling** (do BEFORE batch-ingesting more videos):
   replace fixed 10s sampling in `workers/ingest/src/ingest/media.py::
   extract_frames` with ffmpeg scene filter + perceptual-hash dedupe. Cuts
   caption/embed cost 3–10× per video and removes near-duplicate noise from
   the visual index (should help visual MRR too).
6. **BM25 corpus refit is O(N²)** across ingests
   (`workers/ingest/src/ingest/pipeline.py::_refresh_corpus_bm25_stats`
   re-reads every transcript from S3 per video). Merge per-video stats
   instead. Do alongside #5 before library expansion.

## Things to take care of / loose ends

- **Deploy needed**: the grounded-flag prompt only reaches the live API after
  `cdk deploy` rebuilds the Lambda container. CI green ≠ deployed. Smoke the
  prod endpoint after deploying; remember the query cache (DynamoDB
  `query_cache`, 1h TTL) can serve pre-change answers — use a cache-busting
  query when smoking.
- The demo chip `"today's weather"` on the search page still refuses, now via
  the evidence gate / grounded flag (verified in eval). Better story anyway.
- Eval runs cost real Bedrock/Pinecone (small, AWS credits): full 7-config run
  ~15 min; scoped single-config baseline trick is in `lessons.md`.
- README "145 eval queries" mentions may be stale → should say 135 (check
  `README.md` and dashboard copy).
- `.claude/launch.json` got `autoPort: true` (gitignored, local only) because
  port 3000 was occupied.
- Frontend checks before web commits: `pnpm --filter web lint && typecheck
  && build` — the eval `AnimatedNumber` had a `set-state-in-effect` lint trap;
  pattern to reuse: render the target value directly under reduced motion.
