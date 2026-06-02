# Ingestion worker image (ECS Fargate). Python 3.12 + ffmpeg.
FROM python:3.12-slim

# ffmpeg is required for frame and audio extraction.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build from the repo root:
#   docker build -f workers/ingest/Dockerfile .
COPY packages/shared ./packages/shared
COPY workers/ingest ./workers/ingest
RUN pip install --no-cache-dir ./packages/shared ./workers/ingest

CMD ["python", "-m", "ingest.main"]
