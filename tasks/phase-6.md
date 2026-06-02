# Phase 6 — Deployment and Observability — TODO

Ship the Phase 5 app to production-like AWS/Vercel infrastructure with runtime secrets,
cost controls, CloudWatch observability, and live smoke coverage.

Conventions: granular conventional commits, push frequently, no `Co-Authored-By` trailer.

## Tasks

- [x] A. FastAPI Lambda container behind API Gateway
- [x] B. Secrets Manager runtime overlay for Pinecone/LangSmith/admin/session secrets
- [x] C. DynamoDB query cache and public rate-limit controls
- [x] D. Fargate worker task, EventBridge dispatcher, and empty-queue worker smoke
- [x] E. CloudWatch log groups, dashboard, and API/DLQ alarms
- [x] F. Vercel production web deployment against the deployed API
- [x] G. Production CORS for the Vercel origin
- [x] H. Live smoke tests over API, web, search, dispatcher, worker, and alarms
- [x] I. README, CLAUDE, and task log update after live smoke

## Guardrails

- Do not redo Phase 0 foundations.
- Do not disturb Phase 1-5 contracts, UI structure, retrieval flow, or eval data.
- Keep all secret values out of logs and git.
- Keep deploy fixes granular and pushed frequently.
- Treat manual Fargate launch with an empty queue as an image/runtime smoke, not a real ingest job.

## Review

**Outcome:** Phase 6 is complete. The application is deployed with AWS-hosted API/runtime
infrastructure and a Vercel production frontend, with live health, CORS, query, dispatcher, worker,
dashboard, and alarm smoke checks passing.

**Production endpoints**
- API: `https://fsd8xleob9.execute-api.us-east-1.amazonaws.com/`
- Web: `https://multimodal-video-rag-web.vercel.app`
- Vercel deployment: `dpl_FTVMYUHNUpU4Zi9UhrEZXXXnods6`

**AWS resources**
- Stack: `VideoRagCore` (`UPDATE_COMPLETE`)
- API Lambda: `video-rag-api`
- API Gateway: `video-rag-api`
- Worker cluster: `video-rag-worker`
- Worker task definition: `arn:aws:ecs:us-east-1:159480939084:task-definition/video-rag-ingest:5`
- Dispatcher Lambda: `video-rag-worker-dispatcher`
- Runtime secret: `video-rag/runtime`
- Query controls: DynamoDB tables `query_cache` and `rate_limits`
- Dashboard: `video-rag-phase6`
- Alarms: API error alarm and ingest DLQ alarm both `OK`

**Live smoke (2026-06-02)**
- API health: `GET /health` -> `200 {"status":"ok"}`
- Vercel page: `GET https://multimodal-video-rag-web.vercel.app/` -> `200`
- Production CORS preflight from Vercel origin: `OPTIONS /api/search` -> `200`, with
  `Access-Control-Allow-Origin: https://multimodal-video-rag-web.vercel.app`
- Public library from Vercel origin: `GET /api/videos` -> `200`, 3 demo videos
- Real search from Vercel origin: `POST /api/search` for `QkdBXUikRQc` -> `200`, grounded answer
  with transcript/visual citations
- Dispatcher smoke: invoke `video-rag-worker-dispatcher` -> `{"started": false, "reason": "empty_queue"}`
- Worker smoke: manual Fargate run on task definition revision 5 -> container exit code `0`
- Worker logs: `worker_start`, `worker_poll_empty`, `worker_exit messages_processed=0`
- API logs: request log lines for health, preflight, videos, and search all show status `200`

**Vercel notes**
- Project: `multimodal-video-rag-web`
- Root directory: `apps/web`
- Build command: `pnpm --filter web build`
- Install command: `pnpm install --frozen-lockfile --ignore-scripts`
- Production env: `NEXT_PUBLIC_API_BASE_URL=https://fsd8xleob9.execute-api.us-east-1.amazonaws.com`

**Known follow-up**
- Production deploy is public-demo grade, not hardened multi-tenant auth. Add custom domain, WAF,
  stricter origin management, and deeper ingestion failure alarms before treating it as a real
  customer-facing service.
