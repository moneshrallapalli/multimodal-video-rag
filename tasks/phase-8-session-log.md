# Phase 8 — running session log

Live log for the Phase 8 quality sessions. If a session gets cut off, the next
one starts here: read `phase-8-quality.md` for the full handoff (plan, metrics,
the stale-baseline incident), then this file for what has actually happened
since. Append a dated entry per session; never rewrite old entries.

---

## Session 2026-06-11 (b) — context load + state verification

**Status: session start. No code changes yet.**

### What was done
- Read the handoff docs: `phase-8-quality.md`, `lessons.md`, `todo.md`.
- Verified repo state: HEAD at `797d282` (the handoff commit), working tree
  clean, all Phase 8 session-(a) work pushed.
- Verified the committed eval artifact is current:
  `apps/web/src/data/eval-results.json` meta says 135 queries, 13 videos,
  judge=haiku, `generated_at: 2026-06-11T13:28:38+00:00` — matches the rebuilt
  golden set. The staleness trap from session (a) is NOT currently present.

### Findings (not yet fixed)
- **README is stale, but differently than the handoff guessed.** The handoff
  said README might say "145 queries"; it actually says **"14 indexed videos,
  150 hand-labeled queries"** (`README.md:28`) and quotes judge numbers
  (quality 0.854, grounded 0.959, correct 0.805, n=123 — `README.md:39`) that
  don't match the current artifact (quality 0.85, grounded 0.94, correct 0.75,
  useful 0.94, n=110, on 135 queries / 13 videos). Reconcile README copy with
  the artifact when touching docs. Also re-check the dashboard methodology
  copy for the same numbers.

### Still outstanding from the session-(a) handoff
- **`cdk deploy` not yet run/verified** — the grounded-flag answer prompt
  (`55f8c9c`) only reaches the live API after the Lambda container rebuilds.
  CI green ≠ deployed. After deploying, smoke prod with a cache-busting query
  (DynamoDB `query_cache` has a 1h TTL and can serve pre-change answers).
- The six-item score-improvement plan in `phase-8-quality.md` — none started:
  1. Over-refusal tuning (13 wrongly-refused queries; precision 0.458 → ≥0.6)
  2. The 1 missed refusal
  3. Judge correct_rate 0.75 (~27 incorrect answers)
  4. Rewrite-on-miss + parallel transcript/visual retrieval
  5. Scene-detection frame sampling (BEFORE batch-ingesting more videos)
  6. BM25 O(N²) corpus refit merge (alongside #5)

### Next action when work resumes
Start plan item 1: add per-query refusal provenance to the eval run so each of
the 13 over-refusals is attributed to either the retrieval gate
(`packages/graph/src/graph/pipeline.py::_apply_retrieval_gate`, thresholds in
`models.py`) or the LLM `grounded=false`
(`packages/graph/src/graph/answering.py::_prompt`), then tune the dominant
layer. Remember the scoped-baseline trick from `lessons.md` (monkeypatch
`run_eval.CONFIGS` to one config, ~5 min) before any A/B.

---

## Session 2026-06-11 (b) continued — plan item 1: over-refusal tuning

### Attribution (offline, zero cost — from the committed artifact)
Gate refusals carry the canned `no_answer_message`; `grounded=false` refusals
carry the LLM's own text. Result: **all 13 over-refusals AND all 11 correct
refusals are LLM `grounded=false`; the retrieval gate fires on zero golden
queries under production config.** Thresholds are the wrong lever entirely.
Two failure patterns in the 13:
1. **Answers-then-refuses** (e008, e104, e116): substantive cited answer text
   with `grounded=false` — partial (visual-half) evidence treated as ungrounded.
2. **Exact-timestamp pedantry** (e016, e024, e044): refuses "at the 2:05 mark"
   because no frame sits at exactly 2:05 (frames sample every ~10s).
Also: 9/13 already had `intent=visual` → the old visual-only leniency rules
were present and insufficient.

### Changes landed (pushed after verification)
- `6fe9405` — refusal provenance: `refusal_reason`
  (empty_query / retrieval_gate / no_candidates / llm_ungrounded /
  pipeline_error) stamped at each refusal site, surfaced on `SearchResponse`,
  recorded in eval per-query records. Tests assert reasons.
- `881c61b` — prompt rewrite in `answering.py::_prompt`: grounded ⇔ "answer
  states context info addressing the question, even partially/approximately";
  ±15s timestamp tolerance; caption tolerance now unconditional (all intents);
  refusal retained for topic-adjacent context lacking the asked-for info
  (protects the 11 true refusals, which are all absent-topic questions).
- ruff + 130 tests green before commit.

### Missed-refusal finding (plan item 2 — needs a user decision, do NOT
"fix" via prompt)
e100 ("Does this video include instruction on advanced yoga poses…") — golden
labels it no_answer, but the model gives a grounded, correct "No, this is a
beginner workout" citing real evidence at 16:46; the golden row's own notes
describe exactly that answer. Recommendation: relabel e100 as answerable
(negative-existence answer) rather than nudging the prompt to refuse — a
prompt that refuses evidenced "No" answers makes the product worse to game a
label. Golden edits change denominators → regen baseline after.

### A/B in flight
Scoped production-only eval (no judge) running against
`eval/golden/expanded.jsonl` → `/tmp/eval-prod-grounded-v2.json`.
Baseline = committed artifact (same golden set, generated 2026-06-11 13:28):
no-answer F1 0.611 / precision 0.458 / recall 0.917, MRR 0.791, ts@5s 0.740.
Targets: precision ≥0.6 (≥6 of 13 over-refusals converted), recall ≥0.917
(no new missed refusals beyond e100), MRR/ts@5s unchanged (retrieval untouched).
If targets met: re-run full eval with judge to regenerate the committed
artifact, then `cdk deploy` (still outstanding) ships provenance + prompt
together.
