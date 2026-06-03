# Ingestion worker image (ECS Fargate). Python 3.12 + ffmpeg.
FROM python:3.12-slim

# ffmpeg is required for frame and audio extraction.
# deno is required by yt-dlp for YouTube JS extraction (deprecated without it).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl unzip \
    && curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && apt-get purge -y curl unzip && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build from the repo root:
#   docker build -f workers/ingest/Dockerfile .
COPY packages/shared ./packages/shared
COPY workers/ingest ./workers/ingest
RUN pip install --no-cache-dir ./packages/shared ./workers/ingest

CMD ["python", "-m", "ingest.main"]
