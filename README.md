# Multimodal Video RAG

Ask questions about a video and get timestamped answers grounded in what was actually said and shown. Searches over both visual frames and spoken transcript, refuses to answer when the evidence is weak, and cites the exact moment.

Built end-to-end on AWS. Ingestion is async (SQS + Fargate), retrieval is a LangGraph pipeline with hybrid dense/sparse search and cross-encoder reranking, answers come from Bedrock Claude Haiku with grounded citations. 87 tests, 6 ablation configs, deployed to production.

## How it works

1. Admin submits a YouTube URL through the web console.
2. A Fargate worker pulls the video, extracts keyframes every 30s, transcribes the audio, then embeds both modalities (Titan Text v2 for transcript chunks, Titan Multimodal G1 for frames) into separate Pinecone indexes.
3. When a user asks a question, a LangGraph pipeline classifies intent, retrieves from the relevant index(es), fuses results with Reciprocal Rank Fusion, reranks, gates on evidence strength, and generates a grounded answer via Bedrock.
4. The response includes the answer, confidence score, and clickable timestamped citations.

The system knows the difference between "what did she say about planning?" (transcript) and "show me the whiteboard" (visual). It also knows when to say "I don't have evidence for that."

## Architecture

![VideoRAG architecture](docs/assets/video-rag-architecture.png)

```
Browser (Next.js on Vercel)
    |
    | same-origin proxy
    v
FastAPI (Lambda container, ARM64)
    |
    |--- /api/search ---> LangGraph pipeline
    |                         |
    |                         |--> Pinecone transcript index (dotproduct, 1024-dim)
    |                         |--> Pinecone visual index (cosine, 1024-dim)
    |                         |--> BM25 sparse vectors (hybrid blend)
    |                         |--> bge-reranker-base (cross-encoder)
    |                         |--> Bedrock Claude Haiku 4.5 (answer generation)
    |                         |--> LangSmith (tracing)
    |
    |--- /api/admin ---> DynamoDB + SQS
                              |
                              v
                     Fargate worker (ingestion)
                         |--> ffmpeg (frames)
                         |--> Whisper via Bedrock (transcription)
                         |--> Titan embeddings (dense + sparse)
                         |--> S3 (artifacts)
                         |--> Pinecone (vectors)
```

Infrastructure is all CDK (Python). VPC with gateway endpoints, least-privilege IAM scoped to specific model ARNs, Secrets Manager for runtime config, CloudWatch dashboard with alarms.

## Eval results

Real evaluation over indexed content. 15 hand-labeled queries across transcript, visual, timestamp, hybrid, and no-answer types. Honest numbers from a deterministic harness (no cherry-picking, no LLM judge yet).

| Config | Recall@5 | MRR | Timestamp@5s | No-answer F1 |
|---|---:|---:|---:|---:|
| Dense baseline | 1.00 | 0.90 | 0.83 | 0.80 |
| Hybrid (dense + BM25) | 1.00 | 0.90 | 0.83 | 0.80 |
| **Hybrid + cross-encoder rerank** | **1.00** | **0.96** | **0.92** | **0.80** |
| Hybrid + query rewrite | 1.00 | 0.90 | 0.83 | 0.50 |

The cross-encoder rerank config is the winner. MRR jumped from 0.90 to 0.96 and timestamp accuracy went from 83% to 92%. Query rewrite actually hurt no-answer F1 on this seed (it rewrites away from the original phrasing, making the refusal gate less precise). I kept it in the ablation table because that's a real finding, not a reason to hide it.

## Interesting engineering decisions

**Two Pinecone indexes, not one.** Transcript uses dotproduct (since Titan Text v2 embeddings are normalized, dotproduct = cosine but faster). Visual uses cosine because Titan Multimodal G1 embeddings aren't consistently normalized. Mixing them in one index would require a single similarity metric that works poorly for one modality.

**Per-modality retrieval gates.** A transcript score of 0.3 means something different from a visual score of 0.3 (different embedding models, different metrics). The refusal gate checks each modality against its own threshold. This fixed a class of bugs where near-tied scores caused the wrong modality to win.

**BM25 sparse vectors alongside dense.** The hybrid path alpha-blends dense Titan vectors with sparse BM25 term frequencies on the same Pinecone query. This helps with exact-match queries ("what does she say about proper planning?") where dense embeddings alone rank a semantically-similar but wrong chunk higher.

**Idempotent ingestion.** SQS delivers at-least-once. The worker checks job status in DynamoDB before doing any expensive work (downloads, transcription, embedding). A redelivered message for a completed job gets a log line and a delete, not a duplicate $2 Bedrock bill.

**Cross-encoder baked into the Docker image.** `sentence-transformers` + `BAAI/bge-reranker-base` is ~500MB. It's pre-downloaded into the Lambda container image at build time so cold starts don't hit Hugging Face.

## Project layout

```
apps/web/          Next.js frontend (search UI, admin console, eval dashboard)
apps/api/          FastAPI backend (Lambda container)
workers/ingest/    Fargate ingestion worker
packages/graph/    LangGraph query pipeline
packages/shared/   Config, models, Pinecone/Bedrock/S3 clients, BM25 encoder
eval/              Golden dataset + deterministic evaluation harness
infra/             AWS CDK (VPC, Lambda, Fargate, SQS, DynamoDB, IAM, CloudWatch)
```

## Run locally

You need [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/). Copy `.env.example` to `.env` and fill in your keys.

```bash
uv sync --all-packages
uv run uvicorn api.main:app --reload        # API at localhost:8000

pnpm install
pnpm --filter web dev                       # Frontend at localhost:3000
```

The frontend proxies `/api/*` to the backend via Next.js rewrites, so everything works same-origin with no CORS setup.

```bash
uv run pytest -q                            # 87 tests
uvx ruff check . && uvx ruff format --check .
pnpm --filter web lint && pnpm --filter web build
```

## Tech

- **LLM:** AWS Bedrock, Claude Haiku 4.5 (answer generation + query rewrite)
- **Embeddings:** Titan Text Embedding v2 (transcript), Titan Multimodal G1 (visual frames)
- **Reranking:** bge-reranker-base (cross-encoder, CPU inference in Lambda)
- **Vector DB:** Pinecone serverless (2 indexes: transcript dotproduct, visual cosine)
- **Orchestration:** LangGraph (stateful query pipeline with 9 nodes)
- **Backend:** FastAPI, Pydantic, deployed as ARM64 Lambda container
- **Frontend:** Next.js, TypeScript, Tailwind, shadcn/ui
- **Infra:** CDK (Python), S3, SQS, ECS Fargate, DynamoDB, API Gateway, CloudWatch
- **Eval:** Custom deterministic harness (Recall@K, MRR, Timestamp@Ns, modality accuracy, no-answer F1)
- **Observability:** LangSmith tracing, CloudWatch dashboard + alarms, structured logging

## Live

- Web: https://multimodal-video-rag-web.vercel.app
- API: https://fsd8xleob9.execute-api.us-east-1.amazonaws.com/

## License

MIT
