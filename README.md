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

## Status

Early development — foundations and scaffolding in place.

## License

[MIT](./LICENSE)
