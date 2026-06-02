#!/usr/bin/env python
"""Sync local runtime secrets into AWS Secrets Manager.

The deployed API and worker read this JSON secret by name. The script reports
which keys are present, but never prints secret values.
"""

from __future__ import annotations

import argparse
import json

import boto3
from botocore.exceptions import ClientError
from shared import settings

SECRET_FIELDS = {
    "PINECONE_API_KEY": "pinecone_api_key",
    "LANGSMITH_API_KEY": "langsmith_api_key",
    "ADMIN_PASSWORD_HASH": "admin_password_hash",
    "SESSION_SECRET": "session_secret",
}
REQUIRED_KEYS = {"PINECONE_API_KEY", "ADMIN_PASSWORD_HASH", "SESSION_SECRET"}


def _secret_payload() -> dict[str, str]:
    payload = {
        env_name: str(getattr(settings, field_name))
        for env_name, field_name in SECRET_FIELDS.items()
        if getattr(settings, field_name)
    }
    missing = sorted(REQUIRED_KEYS - payload.keys())
    if missing:
        raise SystemExit(f"Missing required local secret values: {', '.join(missing)}")
    return payload


def _secret_exists(client, name: str) -> bool:
    try:
        client.describe_secret(SecretId=name)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return False
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="video-rag/runtime", help="Secrets Manager secret name")
    parser.add_argument("--region", default=settings.aws_region)
    args = parser.parse_args()

    payload = _secret_payload()
    client = boto3.client("secretsmanager", region_name=args.region)
    secret_string = json.dumps(payload)
    if _secret_exists(client, args.name):
        client.put_secret_value(SecretId=args.name, SecretString=secret_string)
        action = "updated"
    else:
        client.create_secret(Name=args.name, SecretString=secret_string)
        action = "created"

    print(f"{action} secret {args.name} with keys: {', '.join(sorted(payload))}")


if __name__ == "__main__":
    main()
