# api

FastAPI backend. Exposes the public query endpoint and the admin ingestion
endpoints. Wraps the `graph` query pipeline; deployed on Lambda + API Gateway.

```bash
uv run uvicorn api.main:app --reload
```
