"""Centralized, typed configuration loaded from the environment.

Every service imports `settings` from here so configuration lives in one
place and is validated at startup.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

_SECRET_ENV_TO_FIELD = {
    "PINECONE_API_KEY": "pinecone_api_key",
    "LANGSMITH_API_KEY": "langsmith_api_key",
    "ADMIN_PASSWORD_HASH": "admin_password_hash",
    "SESSION_SECRET": "session_secret",
}


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
    dynamodb_query_cache_table: str = ""
    dynamodb_rate_limit_table: str = ""

    # Deployment secrets (optional JSON secret with env-style keys).
    secrets_manager_secret_name: str = ""

    # Ingestion worker tuning
    ingest_frame_interval_seconds: int = 30
    ingest_max_frames: int = 20
    whisper_model_size: str = "tiny.en"
    transcript_chunk_seconds: int = 30
    transcript_chunk_overlap_seconds: int = 6

    # Query pipeline feature flags
    enable_hybrid_transcript: bool = True
    enable_cross_encoder_rerank: bool = False
    enable_query_rewrite: bool = True
    hybrid_alpha: float = 0.7
    search_config_version: str = "hybrid-rewrite-v1"

    # Admin auth
    admin_password_hash: str = ""
    session_secret: str = ""
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"

    # Local dev / CORS (comma-separated origins allowed to call the API)
    cors_allow_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,https://multimodal-video-rag-web.vercel.app"
    )

    # Public query cost controls. Disabled unless tables are configured.
    query_cache_ttl_seconds: int = 3600
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 20

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


def _coerce_secret_fields(secret: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in secret.items():
        field_name = _SECRET_ENV_TO_FIELD.get(key.upper(), key.lower())
        if field_name in Settings.model_fields and value not in (None, ""):
            values[field_name] = value
    return values


def _load_secrets_manager_values(base: Settings) -> dict[str, Any]:
    if not base.secrets_manager_secret_name:
        return {}

    import boto3

    client = boto3.client("secretsmanager", region_name=base.aws_region)
    response = client.get_secret_value(SecretId=base.secrets_manager_secret_name)
    secret_string = response.get("SecretString")
    if not secret_string:
        return {}
    raw_secret = json.loads(secret_string)
    if not isinstance(raw_secret, dict):
        raise ValueError("Runtime secret must be a JSON object")
    return _coerce_secret_fields(raw_secret)


def _hydrate_secret_environment(secret_values: dict[str, Any]) -> None:
    for env_name, field_name in _SECRET_ENV_TO_FIELD.items():
        value = secret_values.get(field_name)
        if value:
            os.environ[env_name] = str(value)


@lru_cache
def get_settings() -> Settings:
    base = Settings()
    secret_values = _load_secrets_manager_values(base)
    if not secret_values:
        return base
    _hydrate_secret_environment(secret_values)
    merged = base.model_dump()
    merged.update(secret_values)
    return Settings(**merged)


settings = get_settings()
