"""Centralized, typed configuration loaded from the environment.

Every service imports `settings` from here so configuration lives in one
place and is validated at startup.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AWS
    aws_region: str = "us-east-1"

    # Bedrock model IDs (confirmed working 2026-06, us-east-1)
    bedrock_llm_model_id: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_text_embed_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_image_embed_model_id: str = "amazon.titan-embed-image-v1"
    embed_dim: int = 1024

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_transcript_index: str = "transcript"
    pinecone_visual_index: str = "visual"

    # LangSmith
    langsmith_tracing: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = "multimodal-video-rag"

    # AWS resources
    s3_bucket: str = ""
    sqs_queue_url: str = ""
    dynamodb_videos_table: str = "videos"
    dynamodb_jobs_table: str = "jobs"

    # Ingestion worker tuning
    ingest_frame_interval_seconds: int = 30
    ingest_max_frames: int = 20
    whisper_model_size: str = "tiny.en"

    # Admin auth
    admin_password_hash: str = ""
    session_secret: str = ""

    # Local dev / CORS (comma-separated origins allowed to call the API)
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
