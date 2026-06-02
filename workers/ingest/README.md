# ingest

Long-running ingestion worker. In Phase 2 it can run locally against the deployed SQS,
DynamoDB, and S3 resources; in Phase 6 it becomes the ECS/Fargate task.

Current pipeline:

```text
SQS message
-> DynamoDB job status updates
-> yt-dlp metadata/video download
-> ffmpeg audio + interval frame extraction
-> faster-whisper transcript
-> S3 artifacts
-> DynamoDB video record
```

Phase 3 adds Bedrock Titan embeddings and Pinecone upserts.

## Run Locally

From the repo root:

```bash
uv sync --all-packages
INGEST_MAX_FRAMES=2 INGEST_FRAME_INTERVAL_SECONDS=120 WHISPER_MODEL_SIZE=tiny.en \
  uv run python -m ingest.main
```

Required `.env` values: `AWS_REGION`, `S3_BUCKET`, `SQS_QUEUE_URL`,
`DYNAMODB_JOBS_TABLE`, and `DYNAMODB_VIDEOS_TABLE`. AWS credentials come from
`~/.aws/credentials`.

Artifacts are written under:

```text
videos/{video_id}/source/metadata.json
videos/{video_id}/audio/audio.m4a
videos/{video_id}/frames/frame_000001.jpg
videos/{video_id}/frames/frames.json
videos/{video_id}/transcript/transcript.json
```

## Docker

Build from the repo root so the worker can install `packages/shared`:

```bash
docker build -f workers/ingest/Dockerfile .
```
