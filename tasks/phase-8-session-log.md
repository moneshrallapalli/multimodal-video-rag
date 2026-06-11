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

### A/B round 1 (scoped, /tmp/eval-prod-grounded-v2.json)
F1 0.611→0.625, precision 0.458→0.500 (13→10 over-refusals), MRR 0.791→0.810,
ts@5s 0.740→0.756 (converted refusals recover retrieval credit). BUT recall
0.917→0.833: new missed refusal e010 — the model restitched comfort-zone
advice as the asked-for "procrastination techniques".

### Key diagnostic: the remaining 10 over-refusals are NOT prompt-fixable
Retrieval-only dump of their contexts showed the LLM refuses honestly:
- **Retrieval misses** (golden chunk absent from top-10 context): e024, e044,
  e052, e077, e084, e097, partially e086. E.g. e024 asks about the 1:25 frame;
  the 1:25 caption is simply not retrieved.
- **Bare visual hits**: image-embedding `visual` entries carry snippet
  "Visual frame from <title> at <ts>." with NO descriptive text (e074's 10:05
  hit, e084's 2:35 hit). The evidence pointer arrives; the content doesn't.
  → Concrete fix for plan item 5: enrich bare visual hits with their frame's
  caption text (the caption exists as a sibling index entry) at index or
  query time. Also feeds item 4 (rewrite-on-miss may pull the right chunk).
Pushing the prompt harder would force hallucination — stopped there.

### Round 2: subject guard (`80811b0`)
Added to the partial-evidence rule: related material on a different subject is
not partial evidence. Spot-check (7 sensitive queries): e010/e020/e050 refuse,
e008/e104/e116 still answer, e077 still refuses (known retrieval miss).
Expected final: ~P 0.524 / R 0.917 / F1 0.667 vs baseline F1 0.611. Precision
target 0.6 NOT met — remaining gap is retrieval/caption-bound (items 4/5),
which is the honest stopping point for item 1.

### Final numbers (full 7-config run + judge, artifact committed `6cf4dc9`)
Production vs baseline: no-answer F1 0.611→**0.629**, precision 0.458→0.478,
recall held 0.917 (e100 only miss). MRR 0.794 (~unchanged), ts@5s 0.740
(unchanged). Judge (n=111): quality 0.845, grounded 0.928,
correct **0.766** (was 0.75), useful 0.937.
- All 12 remaining over-refusals are `llm_ungrounded` (provable from the new
  per-query `refusal_reason`); the gate fires on zero golden queries.
- Two borderline queries (e018, e099 — asked-for specifics absent from
  retrieved context) flip run-to-run at the grounded borderline; e008/e104/
  e116 (answers-then-refuses) stayed converted.
- Precision target 0.6 not reached — the residual is retrieval/caption-bound
  (see diagnostic above), so further gains belong to items 4/5, not the prompt.

### Item 1 status: DONE (prompt-side ceiling reached)

### Deploy + smoke: DONE
- `cdk deploy VideoRagCore` succeeded (110s, cached layers). Live smoke with
  cache-busting queries: answerable query → grounded cited answer,
  `refusal_reason: null`; off-domain query → refused with
  `refusal_reason: "llm_ungrounded"`. Prompt + provenance are serving.
- README refreshed (`ccc96c7`): 135/13 counts, current per-config table,
  judge n=111, and corrected the stale "cross-encoder is eval-only" claim
  (it ships in the `video-rag-reranker` Lambda since Phase 6).

### e100 relabel: APPROVED by user and done (`95ab8c7`)
Relabeled no_answer → transcript with relevant span 1006.48–1038.4 (the 16:46
"crazy pretzel shapes" segment) and a reference negative answer. Rationale in
the row notes and commit message: grounded negative-existence answers beat
refusals when direct evidence exists. No-answer denominator 12 → 11; full
artifact regen launched right after (background) — expect recall 1.0 if the
11 true refusals hold, precision ~0.478, F1 ~0.647, small MRR lift from
e100's rank-1 evidence. Commit the regenerated artifact when it lands.

### Open items going into the next session
- Plan items 3–6 from `phase-8-quality.md` (judge correct_rate, rewrite-on-
  miss + parallel retrieval, scene-detection sampling, BM25 refit). Items 4/5
  now have a sharper target: the 12 residual over-refusals are retrieval
  misses + bare visual hits (see diagnostic) — enriching bare visual hits
  with their frame-caption text is the concrete first move.
