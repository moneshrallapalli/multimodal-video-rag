# ingest

Long-running ingestion worker that runs as an ECS Fargate task, pulled from
SQS. Extracts scene keyframes, transcribes audio (faster-whisper), aligns
transcript chunks to timestamps, embeds both modalities with Bedrock Titan,
and upserts vectors to Pinecone while tracking job status in DynamoDB.
