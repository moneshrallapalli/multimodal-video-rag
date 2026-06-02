"""Config helpers used by deployed runtimes."""

from __future__ import annotations

import os

from shared.config import _coerce_secret_fields, _hydrate_secret_environment


def test_secret_keys_accept_env_style_names():
    values = _coerce_secret_fields(
        {
            "PINECONE_API_KEY": "pinecone",
            "LANGSMITH_API_KEY": "langsmith",
            "ADMIN_PASSWORD_HASH": "hash",
            "SESSION_SECRET": "session",
        }
    )

    assert values == {
        "pinecone_api_key": "pinecone",
        "langsmith_api_key": "langsmith",
        "admin_password_hash": "hash",
        "session_secret": "session",
    }


def test_secret_values_hydrate_process_environment(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    _hydrate_secret_environment({"langsmith_api_key": "langsmith"})

    assert os.environ["LANGSMITH_API_KEY"] == "langsmith"
