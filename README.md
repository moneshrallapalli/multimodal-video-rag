# Multimodal Video RAG

VideoRAG is a deployed search app for long-form video. Ask a question, and it returns the transcript chunks or visual frames that support the answer, with timestamps back to the source moment.

The frontend runs on Vercel, and the backend is AWS-native: FastAPI in a Lambda container, SQS/Fargate ingestion, S3 artifacts, Pinecone indexes, LangGraph retrieval, and Bedrock Claude Haiku for answer generation and query rewrite. If retrieval is weak, the app refuses instead of guessing.

## How it works

1. Admin submits a YouTube URL through the web console.
2. A Fargate worker downloads the video, extracts keyframes every 30 seconds, transcribes the audio with faster-whisper, and embeds both modalities into separate Pinecone indexes.
3. When a user asks a question, a LangGraph pipeline classifies intent, retrieves from one or both indexes, fuses results with Reciprocal Rank Fusion, reranks, gates on evidence strength, and generates a grounded answer via Bedrock.
4. The response includes the answer, confidence score, and clickable timestamped citations.

Transcript questions and visual questions follow different retrieval paths. For example, "what did she say about planning?" leans on transcript chunks, while "show me the whiteboard" leans on frame search.

## Architecture

![VideoRAG architecture](docs/assets/video-rag-architecture.png)

The web app calls the API through same-origin rewrites. Search requests run through FastAPI and a 9-node LangGraph pipeline. Ingestion runs asynchronously through DynamoDB, SQS, EventBridge, and Fargate. Transcript vectors and visual vectors stay in separate Pinecone indexes because they use different models and scoring behavior. S3 keeps the derived artifacts, LangSmith traces the query pipeline, and CloudWatch tracks operational health.

Runtime note: the API Lambda is sized at 2048 MB to leave headroom for controlled CPU cross-encoder runs.

Infrastructure is CDK in Python, with least-privilege IAM, Secrets Manager runtime config, VPC endpoints where they matter, and alarms for the paths that should wake someone up.

## Eval results

Real evaluation over 13 indexed videos, 145 hand-labeled queries (transcript, visual, timestamp, hybrid, summary, no-answer). Deterministic retrieval metrics plus Haiku LLM judge on answerable queries.

| Config | MRR | Timestamp@5s | No-answer F1 |
|---|---:|---:|---:|
| Dense only | 0.880 | 0.822 | 0.400 |
| Dense + strict gate | 0.816 | 0.767 | 0.632 |
| Hybrid BM25 | 0.864 | 0.783 | 0.222 |
| Hybrid + rerank | 0.888 | 0.806 | 0.222 |
| Hybrid + rewrite | 0.864 | 0.783 | 0.222 |
| **Production (hybrid + rewrite + answer gen)** | **0.855** | **0.791** | **0.842** |

LLM judge on 123 answerable queries: quality 0.854, grounded 0.959, correct 0.805, useful 0.943.

MRR and Timestamp@5s are the metrics that discriminate between retrieval configs — Recall@5 is near-ceiling. The production config enables answer generation, which lets the LLM refuse when evidence is weak; this drives No-answer F1 from 0.222 (retrieval-only) to 0.842. The cross-encoder rerank config is eval-only — API Gateway's 30s hard timeout makes cold-start model loading impractical without provisioned concurrency.

## Interesting engineering decisions

**Two Pinecone indexes, not one.** Transcript uses dotproduct (since Titan Text v2 embeddings are normalized, dotproduct = cosine but faster). Visual uses cosine because Titan Multimodal G1 embeddings aren't consistently normalized. Mixing them in one index would require a single similarity metric that works poorly for one modality.

**Per-modality retrieval gates.** A transcript score of 0.3 means something different from a visual score of 0.3 (different embedding models, different metrics). The refusal gate checks each modality against its own threshold. This fixed a class of bugs where near-tied scores caused the wrong modality to win.

**BM25 sparse vectors alongside dense.** The hybrid path alpha-blends dense Titan vectors with sparse BM25 term frequencies on the same Pinecone query. This helps with exact-match queries ("what does she say about proper planning?") where dense embeddings alone rank a semantically-similar but wrong chunk higher.

**Idempotent ingestion.** SQS delivers at-least-once. The worker checks job status in DynamoDB before doing any expensive work (downloads, transcription, embedding). A redelivered message for a completed job gets a log line and a delete, not a duplicate $2 Bedrock bill.

**Cross-encoder reranking is eval-only.** `BAAI/bge-reranker-base` (~500MB) is baked into the API container image. In the eval harness it runs locally and moves MRR from 0.920 to 0.934. In the deployed Lambda it can't be used because API Gateway HTTP has a fixed 30-second integration timeout — cold-start model loading always exceeds it. This is a real infrastructure constraint, not a code problem.

## Current limits

- Cross-encoder reranking is eval-only due to API Gateway timeout constraints.
- MRR drops ~3 points from dense-only to production because answer generation trades retrieval precision for refusal accuracy (No-answer F1 0.400 → 0.842).
- Admin ingestion is password-gated, not a multi-user product flow.

## Run locally

You need [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/). Copy `.env.example` to `.env` and fill in your keys.

```bash
uv sync --all-packages
uv run uvicorn api.main:app --reload        # API at localhost:8000

pnpm install
pnpm --filter web dev                       # Frontend at localhost:3000
```

For local admin login, generate `ADMIN_PASSWORD_HASH` and `SESSION_SECRET` with:

```bash
uv run --with argon2-cffi python scripts/init_secrets.py
```

The frontend proxies `/api/*` to the backend via Next.js rewrites, so the browser talks to one origin in local and production.

```bash
uv run pytest -q                            # 117 tests
uvx ruff check . && uvx ruff format --check .
pnpm --filter web lint && pnpm --filter web build
```

## Tech

- **LLM:** AWS Bedrock, Claude Haiku 4.5 (answer generation + query rewrite)
- **Embeddings:** Titan Text Embedding v2 (transcript), Titan Multimodal G1 (visual frames)
- **Transcription:** faster-whisper in the ingestion worker
- **Reranking:** bge-reranker-base (cross-encoder, CPU inference in Lambda)
- **Vector DB:** Pinecone serverless (2 indexes: transcript dotproduct, visual cosine)
- **Orchestration:** LangGraph (stateful query pipeline with 9 nodes)
- **Backend:** FastAPI, Pydantic, deployed as ARM64 Lambda container
- **Frontend:** Next.js, TypeScript, Tailwind, shadcn/ui
- **Infra:** CDK (Python), S3, SQS, ECS Fargate, DynamoDB, API Gateway, CloudWatch
- **Eval:** Custom deterministic harness (Recall@K, MRR, Timestamp@Ns, modality accuracy, no-answer F1) + Haiku LLM judge
- **Observability:** LangSmith tracing, CloudWatch dashboard + alarms, structured logging

## Live

- Web: https://multimodal-video-rag-web.vercel.app
- API: https://fsd8xleob9.execute-api.us-east-1.amazonaws.com/

## License

MIT
