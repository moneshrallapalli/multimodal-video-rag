"""Ingestion worker entrypoint (runs as a Fargate task).

Pulls a job from SQS and runs the pipeline: download -> keyframes ->
transcribe -> chunk + align timestamps -> embed (Titan) -> upsert (Pinecone)
-> update job status (DynamoDB). Implemented in Phase 2.
"""
from __future__ import annotations


def main() -> None:
    raise NotImplementedError("Ingestion pipeline lands in Phase 2.")


if __name__ == "__main__":
    main()
