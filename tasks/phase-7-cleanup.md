# Phase 7 — Pre-Reveal Cleanup

Audit-driven cleanup of correctness, security, and ops gaps found after Phases 2-6
shipped. Source of truth: this file. If session runs out of context, resume from the
first unchecked item.

**Conventions:** granular conventional commits, NO `Co-Authored-By`, push frequently.
Run `uvx ruff check . && uvx ruff format --check . && uv run pytest -q` before every
Python commit; `pnpm --filter web lint && typecheck && build` before every web commit.

**Order of operations:** security first (cheapest, highest payoff), then correctness
bugs, then ops hardening, then larger architectural fills. Each item is independent
and can be committed separately.

---

## 🔴 P0 — Security (block public reveal)

### [x] T1. Refuse empty `session_secret` in deployed mode  ✅ `f835dc7`

**File:** `apps/api/src/api/auth.py` line ~25
**Why:** Production fallback to `"dev-only-insecure-secret"` makes admin cookies
forgeable if Secrets Manager silently drops `SESSION_SECRET`.
**Change:**
```python
def _serializer() -> URLSafeTimedSerializer:
    secret = settings.session_secret
    if not secret:
        if settings.secrets_manager_secret_name:
            raise RuntimeError("SESSION_SECRET missing from runtime secret")
        secret = "dev-only-insecure-secret"
    return URLSafeTimedSerializer(secret, salt="admin-session")
```
**Verify:** existing `test_api.py` still passes (it pins `session_secret` via monkeypatch).
**Commit:** `fix(api): refuse empty session secret in deployed mode`
**Status:** not started

---

### [x] T2. Scope `bedrock:InvokeModel` and `ecs:RunTask` IAM to specific ARNs  ✅ `93c0da5`

**File:** `infra/video_rag_infra/core_stack.py` lines 218-221, 240-245, 403-408
**Why:** `Resource: "*"` with literal `# TODO` comment is the first thing a recruiter
spots; least-privilege violation.
**Change plan:**
- Compute model ARNs from `region` and model IDs.
- Worker role: text embed + image embed only.
- API role: LLM (Claude Haiku 4.5 inference profile) only.
- Dispatcher: scope `ecs:RunTask` to the task-def ARN; `ecs:ListTasks` to the cluster ARN.
**Verify:** `cd infra && cdk synth` succeeds; diff shows narrowed policies.
**Commit:** `fix(infra): scope bedrock and ecs IAM to specific ARNs`
**Status:** not started

---

## 🟠 P1 — Correctness bugs

### [x] T3. Fix off-by-half-interval frame timestamps  ✅ `baf607f`

**File:** `workers/ingest/src/ingest/media.py` lines 97-117
**Why:** `ffmpeg -vf fps=1/30` picks frames from the midpoint of each window
(~t=15 for "frame 1"), not from t=0. Code labels frame 1 as t=0, frame 2 as t=30, etc.
This systematically biases visual Timestamp@5s/@10s metrics low.
**Change:** Shift index-based timestamps by `frame_interval_seconds / 2` since
`fps=1/N` filter's first frame is from `[0, N)` (median t=N/2):
```python
return [
    FrameFile(
        path=path,
        timestamp_seconds=((index - 1) + 0.5) * self.frame_interval_seconds,
    )
    for index, path in enumerate(sorted(frames_dir.glob("frame_*.jpg")), start=1)
]
```
Existing eval-results.json visual timestamps will be re-baselined when T19 runs.
**Verify:** add a test in `workers/ingest/tests/test_pipeline.py` that asserts
first-frame timestamp != 0.
**Commit:** `fix(worker): center frame timestamps on sample window midpoint`
**Status:** not started

---

### [x] T4. Bake the confidence/score scaling constant into config  ✅ `db45438`

**Files:** `packages/graph/src/graph/pipeline.py` lines 221, 268
**Why:** `* 24` is empirically tuned for `rrf_k=60`. Untested, silently breaks if
anyone tunes `rrf_k`. Currently appears in two places without coupling.
**Change:** Add `confidence_scale: float = 24.0` to `GraphConfig` with a comment
explaining "calibrated for rrf_k=60". Replace both inline `* 24` with
`self.config.confidence_scale`. Add a test pinning the conversion.
**Verify:** `uv run pytest packages/graph` green.
**Commit:** `refactor(graph): make confidence scaling configurable`
**Status:** not started

---

### [x] T5. Log + emit metric on bare-except branches  ✅ `3cc678d`

**Files:**
- `apps/api/src/api/search_service.py` lines 22-32
- `packages/graph/src/graph/pipeline.py` line 247

**Why:** Both currently swallow real errors silently as no-answer / extractive
fallback. Operationally indistinguishable from "evidence weak" on the dashboard.
**Change:**
- Add `logger = logging.getLogger(__name__)` and `logger.exception(...)` on each catch.
- Use a structured prefix like `search_pipeline_error` and `bedrock_answer_error`
  so a future CloudWatch metric filter can count them.
**Verify:** add a test asserting the log line emits when the pipeline raises.
**Commit:** `fix(api,graph): log pipeline failures instead of silently refusing`
**Status:** not started

---

### [x] T6. Per-metric score gating for the refusal gate  ✅ `a1176a0`

**File:** `packages/graph/src/graph/pipeline.py` lines 203-221, `models.py`
**Why:** Single `min_source_score=0.2` threshold across dotproduct (transcript)
and cosine (visual) indexes produces the q006 modality flip — both modalities
return similar magnitudes and ties break by insertion order.
**Change:** Add `min_visual_source_score` and `min_transcript_source_score` to
`GraphConfig`; gate per-modality (use the higher of the two when both modalities
present, otherwise the relevant one). Default both to 0.2 for now.
**Verify:** Add a unit test that exercises the visual-tied-with-transcript case
and asserts the correct modality wins. Existing tests stay green.
**Commit:** `fix(graph): gate retrieval per modality to handle metric mismatch`
**Status:** not started

---

## 🟡 P2 — Operations / hardening

### [x] T7. Idempotency short-circuit at top of `IngestionWorker.process()`  ✅ `d6c2e24`

**File:** `workers/ingest/src/ingest/pipeline.py` line 41
**Why:** SQS at-least-once delivery: a redelivered completed job re-downloads,
re-transcribes, re-embeds, costing money + time.
**Change:** Read the job from DDB before starting; if `status == "completed"`,
log and return without raising (so SQS deletes the message).
**Verify:** add test that simulates redelivery and asserts no extra work.
**Commit:** `fix(worker): skip already-completed ingestion jobs`
**Status:** not started

---

### [x] T8. Add retry + jitter to Pinecone HTTP calls  ✅ `3dad8f3`

**File:** `packages/shared/src/shared/pinecone_client.py` lines 83-100
**Why:** Single transient 5xx + bare except = silent no-answer on a network blip.
**Change:** Wrap `_request` with a retry loop: max 2 retries on HTTPError 5xx /
connection errors, exponential backoff with jitter, log each retry.
**Verify:** existing pinecone tests still pass; add a new test for the retry path
with a mock that errors once then succeeds.
**Commit:** `fix(shared): retry transient pinecone failures`
**Status:** not started

---

### [x] T9. Stop buffering ffmpeg output in memory  ✅ `b20d1cc`

**File:** `workers/ingest/src/ingest/media.py` line 150-152
**Why:** `capture_output=True` keeps all stdout+stderr in RAM; ffmpeg progress
can be hundreds of MB on a long video.
**Change:** `subprocess.run(args, check=True, stdout=subprocess.DEVNULL,
stderr=subprocess.PIPE)` — drop stdout, keep stderr (truncated) for diagnostics.
**Verify:** existing worker tests still pass.
**Commit:** `perf(worker): stop buffering ffmpeg stdout in memory`
**Status:** not started

---

### [x] T10. Assert Pinecone index metric matches expectation  ✅ `21aa7fc`

**File:** `packages/shared/src/shared/pinecone_client.py` line 41 area
**Why:** `info.metric` is captured but never validated. A future operator could
rebuild "transcript" as cosine and metrics would drift silently.
**Change:** Accept `expected_metric: str | None` arg on `from_index_name`; if
provided, assert `info.metric == expected_metric`. Pass `"dotproduct"` for the
transcript index, `"cosine"` for visual.
**Verify:** unit test for mismatch raising; smoke still works against live indexes.
**Commit:** `fix(shared): assert pinecone index metric matches expectation`
**Status:** not started

---

### [x] T11. Tighten admin cookie `samesite` to `lax`  ✅ `b802a26`

**File:** `infra/video_rag_infra/core_stack.py` line 194 (`SESSION_COOKIE_SAMESITE`)
**Why:** Vercel rewrites → API means the browser sees same-origin; `lax` is
sufficient and avoids the theoretical CSRF surface that `none` opens.
**Change:** `"SESSION_COOKIE_SAMESITE": "lax"` in `runtime_environment`. Keep
`SECURE=true`. Note in `tasks/lessons.md`: direct browser → API calls (without
the Vercel proxy) will no longer carry the cookie in prod, which matches the
existing architectural decision.
**Verify:** redeploy CDK; admin login via prod web still works.
**Commit:** `fix(infra): tighten admin cookie samesite for same-origin prod path`
**Status:** not started

---

### [x] T12. Add GSI on `jobs` table for created_at-desc ordering  ✅ `801891e`

**File:** `infra/video_rag_infra/core_stack.py` Jobs table + `apps/api/src/api/ingestion_store.py`
**Why:** `scan(Limit=100)` returns scan order, not creation order. Past 100 jobs
the admin table shows stale ordering.
**Change:** Add a GSI `JobsByCreatedAt` (partition `gsi_partition` constant = `"all"`,
sort `created_at`). Update `list_jobs` to `query` the GSI descending with `Limit=100`.
Worker `_update_job` and store `enqueue` set `gsi_partition="all"` on every item.
**Verify:** `cdk synth` succeeds; new `test_ingestion_store` case for the GSI path.
**Commit:** `feat(infra,api): index ingestion jobs by created_at for ordering`
**Status:** not started

---

### [x] T13. Add VPC Gateway Endpoints for S3 and DynamoDB  ✅ `7d3939a`

**File:** `infra/video_rag_infra/core_stack.py` VPC construction (~line 284)
**Why:** Free, reduces traffic through the public NIC, reads better on the
architecture diagram.
**Change:**
```python
vpc.add_gateway_endpoint(
    "S3Endpoint", service=ec2.GatewayVpcEndpointAwsService.S3
)
vpc.add_gateway_endpoint(
    "DynamoDBEndpoint", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB
)
```
**Verify:** `cdk synth` succeeds; new resources appear.
**Commit:** `feat(infra): add S3 and DynamoDB VPC gateway endpoints`
**Status:** not started

---

### [x] T14. Delete stale `eval-sample.json`  ✅ `9362beb`

**File:** `apps/web/src/data/eval-sample.json`
**Why:** No imports reference it; superseded by `eval-results.json`.
**Change:** `rm apps/web/src/data/eval-sample.json`
**Verify:** `pnpm --filter web build` still green.
**Commit:** `chore(web): remove stale eval-sample.json`
**Status:** not started

---

### [x] T15. Refresh `tasks/todo.md` to point at the current phase state  ✅ `2158ddc`

**File:** `tasks/todo.md`
**Why:** Currently still labeled "Phase 1." Confuses anyone clicking into `tasks/`.
**Change:** Replace contents with a short index of per-phase files plus this
cleanup plan.
**Commit:** `docs: refresh tasks/todo.md to reflect current phase state`
**Status:** not started

---

## 🟢 P3 — Larger architectural fills (real ablation honesty)

### [x] T16. BM25 sparse transcript retrieval (hybrid config)  ✅ (4 commits)

Shipped:
- `d07a68f` — pure-python BM25 encoder + tests
- `bbd3fb3` — pinecone sparse vector + hybrid_blend helper
- `5044977` — worker fits BM25 + upserts sparse vectors + persists stats to S3
- `8fb5276` — graph pipeline blends dense+sparse when enabled; loader from S3

Off by default (`GraphConfig.enable_hybrid_transcript=False`). Toggle on in the
eval harness to see hybrid vs dense in the ablation chart.

**Files:** `packages/shared/src/shared/pinecone_client.py` (sparse vector support),
worker `workers/ingest/src/ingest/indexing.py` (fit BM25 encoder + upsert sparse
vectors alongside dense), `packages/graph/src/graph/pipeline.py` (toggle hybrid
on transcript query).
**Why:** Closes the gap between the documented §24.1 ablation
("Dense / Hybrid / +rerank / +rewrite") and the eval's current gate sweep.
**Outline:**
- Add `pinecone-text` to worker deps.
- During ingestion, fit a per-corpus BM25 encoder on all transcript chunks and
  store sparse_values alongside dense in the transcript index (Pinecone serverless
  hybrid).
- In retrieval, send `vector` + `sparse_values` with alpha-weight (default 0.7).
- Add `enable_hybrid_transcript` to `GraphConfig`.
**Commit series:**
- `feat(shared): pinecone sparse vector support`
- `feat(worker): fit BM25 encoder and upsert sparse transcript vectors`
- `feat(graph): hybrid dense+sparse transcript retrieval toggle`
**Status:** not started

---

### [x] T17. bge-reranker rerank stage  ✅ `8051567`

**Files:** `packages/graph/src/graph/retrieval.py` (add `cross_encoder_rerank`
alongside the existing `lexical_rerank`), `apps/api/pyproject.toml` (add
`sentence-transformers`), `apps/api/Dockerfile` (pre-fetch the model into image).
**Why:** Real cross-encoder rerank > lexical heuristic; adds the §24.1 "+rerank" config.
**Outline:**
- `sentence-transformers` is heavy (~500MB); only ship in the API image, not the
  worker. Or run on CPU only.
- Bake model into image: `RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-base')"`.
- Toggle via `GraphConfig.enable_cross_encoder_rerank`.
**Commit:** `feat(graph): bge-reranker rerank stage`
**Status:** shipped

---

### [x] T18. Query rewrite node (Haiku)  ✅ `db0a280`

**Files:** `packages/graph/src/graph/pipeline.py` — add `_rewrite_query` node
between `_classify_intent` and retrieve; set `state["rewritten_query"]`.
**Why:** The `rewritten_query` field already flows through the schema but no
node writes it; fills the §24.1 "+rewrite" config.
**Outline:** Bedrock Haiku rewrite: "Rewrite this video search query to be more
specific and lexically rich, preserving intent. Return only the rewritten query."
Gate behind `GraphConfig.enable_query_rewrite: bool = False`.
**Commit:** `feat(graph): query rewrite node for ablation`
**Status:** shipped

---

### [ ] T19. Re-run eval with the new configs (keep honest framing)

**File:** `eval/run_eval.py` configs list + `docs/evaluation.md` update + commit
fresh `apps/web/src/data/eval-results.json`.
**Outline:** Add `hybrid`, `hybrid_rerank`, `hybrid_rerank_rewrite` configs. Keep
the `"status": "real_seed"` framing — still 1 video, 15 queries.
**Commit:** `eval: refresh seed evaluation with hybrid/rerank/rewrite configs`
**Status:** not started

---

## Final pass

### [ ] T20. Update `tasks/lessons.md` with audit findings

Add entries for:
- Magic constants in retrieval scoring should live in config with a test.
- Bare-except is operational blindness; log + metric.
- Single threshold across two similarity metrics is wrong by construction.
- Frame timestamp drift from `ffmpeg -vf fps` filter offset.
- Cookie samesite should match actual cross-origin reality, not be defensive.

**Commit:** `docs: capture audit lessons`
**Status:** not started

---

## Status snapshot (updated as items complete)

- ✅ Done: T1–T18  (18 / 20) — 90% complete
- 🚧 In progress: T19 (re-run eval)
- ⏳ Remaining: T19 (re-run eval), T20 (lessons)

Last commit pushed: `db0a280` (T18)

**Quick stats (Phase 7 so far):**
- **86 tests passing** (was 51 before this phase) — +35 new tests
- Python lint+format clean repo-wide
- Web lint+typecheck+build clean
- All P0 (security), P1 (correctness), and P2 (ops/hardening) items shipped
- T16 (BM25 hybrid retrieval) shipped end-to-end across 4 commits

**Remaining work is the rest of the §24.1 ablation:** re-run eval (T19), then
capture audit lessons (T20). T17's API Docker image build passed with
`sentence-transformers` and the `BAAI/bge-reranker-base` model baked into the
image; T18's rewrite node is off by default behind `enable_query_rewrite`.
