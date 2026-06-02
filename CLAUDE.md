# CLAUDE.md — Multimodal Video RAG Platform

Context for AI coding assistants working in this repo.

## What this is
An AWS-native multimodal video RAG platform: search and ask questions over long-form
video by visual frames **and** spoken transcript, returning timestamped, grounded
citations. A portfolio-grade AI engineering project aimed at AI/ML roles.

## Current status
- **Phase 0 (foundations): COMPLETE** — AWS account + Bedrock verified, Pinecone (2 indexes),
  LangSmith, repo scaffolded, uv workspace, infra deployed via CDK and smoke-tested.
- **Phase 1 (product skeleton): COMPLETE** — FastAPI + Next.js against typed mocked contracts,
  plus one shared shadcn/ui design system across public search, admin, and eval surfaces.
- **Phase 2 (ingestion pipeline): COMPLETE** — admin API writes DynamoDB/SQS jobs; worker writes
  S3 audio/frame/transcript artifacts and video/job status.
- **Phase 3 (embeddings and Pinecone): COMPLETE** — Phase 2 artifacts are embedded with Titan Text
  v2 / Titan Multimodal G1 and upserted to separate Pinecone transcript/visual indexes.
- **Phase 4 (LangGraph query pipeline): COMPLETE** — `/api/search` uses LangGraph over Pinecone
  transcript/visual retrieval, RRF fusion, retrieval gating, and Bedrock grounded answers.
- **Phase 5 (seed evaluation): COMPLETE** — `eval/golden/seed.jsonl`, `eval/run_eval.py`,
  deterministic metrics, and real `apps/web/src/data/eval-results.json` dashboard data over the
  currently indexed video.
- **Phase 6 (deployment and observability): COMPLETE** — FastAPI Lambda container + API Gateway,
  Fargate worker task/dispatcher, Secrets Manager runtime overlay, DynamoDB query controls,
  CloudWatch dashboard/alarms/logging, and Vercel production web deployment are live-smoked.
- **Next:** expand the demo library/indexes, then deepen eval with more videos, ablations, and
  RAGAS/LLM-judge metrics.

## Architecture
Next.js -> FastAPI (Lambda) -> SQS -> Fargate worker -> S3 / Pinecone / DynamoDB,
with a LangGraph query pipeline -> Bedrock (Claude Haiku 4.5), LangSmith tracing, CloudWatch.

## Layout
- `apps/web` — Next.js frontend (placeholder until Phase 1)
- `apps/api` — FastAPI backend (`/health` live)
- `workers/ingest` — Fargate ingestion worker
- `packages/shared` — typed config (`shared.Settings`), models, clients
- `packages/graph` — LangGraph query pipeline (state schema)
- `eval` — golden dataset + RAGAS / retrieval evaluation
- `infra` — AWS CDK (Python); has its own `.venv`

## Deployed Phase 6 endpoints
- API: `https://fsd8xleob9.execute-api.us-east-1.amazonaws.com/`
- Web: `https://multimodal-video-rag-web.vercel.app`
- CloudWatch dashboard: `video-rag-phase6`
- Runtime secret name: `video-rag/runtime`

## Conventions
- **Python 3.12 via the uv workspace.** From the repo root: `uv sync --all-packages`, then `uv run <cmd>`.
  Do NOT use the system conda Python (it is 3.13).
- **Commits:** small, granular, conventional-commit style; push frequently; **no `Co-Authored-By` trailer**.
- **Secrets:** local `.env` (gitignored) from `.env.example`; never commit secrets or print their values.
  AWS credentials come from `~/.aws/credentials`, not `.env`.
- **Confirmed Bedrock model IDs (us-east-1):** LLM `global.anthropic.claude-haiku-4-5-20251001-v1:0`
  (invoke via the inference profile, not the bare model id); embeddings `amazon.titan-embed-text-v2:0`
  and `amazon.titan-embed-image-v1` (both 1024-dim, but kept in **separate** Pinecone indexes:
  `transcript` = dotproduct, `visual` = cosine).

## Run
```bash
uv sync --all-packages
uv run uvicorn api.main:app --reload     # API at http://127.0.0.1:8000/health
cd infra && cdk synth                     # render infra (uses infra/.venv)
```

## Deeper context
The full design blueprint and week-by-week plan live in the planning docs outside this repo
(`aws-multimodal-video-rag-platform-blueprint.md`). Ask the user for it if you need the full
requirements, the retrieval/eval design, the UI plan, or the phase timeline.
