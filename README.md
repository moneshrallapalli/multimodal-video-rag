# Multimodal Video RAG Platform

Search and ask questions over long-form video by both **visual frames** and **spoken transcript**, returning timestamped, grounded citations. Built AWS-native.

> A production-style AI engineering project: asynchronous ingestion, multimodal retrieval, LangGraph orchestration, Bedrock generation, RAGAS + custom-metric evaluation, and cloud deployment.

## What it does

An admin submits a video; the system extracts keyframes, transcribes the audio, embeds both visual and transcript evidence into Pinecone, and answers natural-language questions with the exact moments as citations. It searches what was *seen* and what was *said* — and refuses to answer when the evidence is weak.

## Architecture (high level)

```text
Next.js  ->  FastAPI  ->  SQS  ->  Fargate worker  ->  S3 / Pinecone / DynamoDB
                                                          |
                              LangGraph query pipeline  ->  Bedrock (Claude Haiku 4.5)
                                                          |
                                       LangSmith tracing  -  CloudWatch metrics
```

## Tech stack

- **Frontend:** Next.js, TypeScript, Tailwind, shadcn/ui
- **Backend:** FastAPI, Pydantic, LangChain, LangGraph
- **AI:** AWS Bedrock — Claude Haiku 4.5 (answers), Titan Multimodal G1 + Titan Text v2 (embeddings)
- **Vector DB:** Pinecone serverless — separate visual and transcript indexes
- **Infra:** S3, SQS, ECS Fargate, DynamoDB, Lambda, CloudWatch (IaC)
- **Eval / Observability:** RAGAS + custom retrieval metrics, LangSmith

## Repository layout

| Path | Purpose |
|---|---|
| `apps/web` | Next.js frontend (public search, admin console, eval dashboard) |
| `apps/api` | FastAPI backend (query + admin endpoints) |
| `workers/ingest` | Fargate ingestion worker (frames, transcription, embeddings) |
| `packages/shared` | Shared config, models, AWS/Pinecone clients |
| `packages/graph` | LangGraph query pipeline |
| `eval` | Golden dataset + RAGAS / retrieval evaluation |
| `infra` | Infrastructure as code |
| `docs` | Architecture and design notes |

## Run locally

Requires the [uv](https://docs.astral.sh/uv/) Python toolchain and [pnpm](https://pnpm.io/).

```bash
# Backend (FastAPI) — http://127.0.0.1:8000
uv sync --all-packages
uv run uvicorn api.main:app --reload

# Frontend (Next.js) — http://localhost:3000  (in a second terminal)
pnpm install
pnpm --filter web dev
```

In dev the browser calls the API same-origin and Next proxies `/api/*` to the backend
(see `apps/web/next.config.ts`), so no CORS setup is needed. Secrets load from `.env`
(copy `.env.example`); the admin login verifies the argon2 `ADMIN_PASSWORD_HASH` produced
by `scripts/init_secrets.py`.

Checks: `uv run pytest` · `uvx ruff check .` · `pnpm --filter web lint && pnpm --filter web typecheck && pnpm --filter web build`.

## Status

- **Phase 0 — Foundations:** complete (AWS + Bedrock verified, Pinecone, CDK infra deployed and smoke-tested).
- **Phase 1 — Product skeleton:** complete — Next.js + FastAPI over typed, mocked contracts, with
  one shared shadcn/ui design system across the public search, admin console, and eval dashboard.
- **Phase 2 — Ingestion pipeline:** core complete — admin API -> DynamoDB/SQS -> worker -> S3/DynamoDB
  smoke-tested locally against deployed AWS resources.
- **Phase 3 — Embeddings and Pinecone:** core complete — Phase 2 artifacts -> Bedrock Titan
  embeddings -> separate Pinecone transcript/visual indexes, with direct retrieval smoke tests.
- **Phase 4 — LangGraph query pipeline:** core complete — `/api/search` now runs real Pinecone
  retrieval, RRF fusion, no-answer gating, and Bedrock grounded answers behind the existing
  frontend contract.
- **Phase 5 — Seed evaluation:** complete — hand-labeled seed golden set, deterministic metrics,
  real committed eval JSON, and dashboard rendering over the current indexed video.
- **Phase 6 — Deployment and observability:** complete — FastAPI deployed as an ARM64 Lambda
  container behind API Gateway, Fargate worker dispatcher on EventBridge, Secrets Manager runtime
  overlay, CloudWatch dashboard/alarms/logging, query cache/rate-limit DynamoDB tables, and Vercel
  production web deployment.
- **Live endpoints:** API `https://fsd8xleob9.execute-api.us-east-1.amazonaws.com/`; web
  `https://multimodal-video-rag-web.vercel.app`.
- **Next:** expand the indexed video library, then deepen eval with more videos, ablations, and
  RAGAS/LLM-judge metrics.

## License

[MIT](./LICENSE)
