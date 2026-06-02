"""Endpoint coverage for the Phase 1 mocked API."""

from __future__ import annotations

import pytest
from api.main import app
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from shared import settings

TEST_PASSWORD = "correct horse battery staple"


@pytest.fixture(autouse=True)
def _admin_secret(monkeypatch):
    """Pin a known admin hash + session secret so tests don't depend on a real .env."""
    monkeypatch.setattr(settings, "admin_password_hash", PasswordHasher().hash(TEST_PASSWORD))
    monkeypatch.setattr(settings, "session_secret", "test-secret-key")
    monkeypatch.setattr(settings, "sqs_queue_url", "")
    monkeypatch.setattr(settings, "pinecone_api_key", "")


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_videos(client):
    r = client.get("/api/videos")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert {v["id"] for v in data} == {"QkdBXUikRQc", "DVtcZQ2QdBg", "as9IYFrTiKc"}
    assert all(v["thumbnail_url"].startswith("https://") for v in data)
    assert {v["id"] for v in data if v["indexed"]} == {"QkdBXUikRQc"}


def test_search_answerable(client):
    r = client.post("/api/search", json={"query": "how to negotiate salary"})
    assert r.status_code == 200
    data = r.json()
    assert data["refused"] is False
    assert data["results"]
    top = data["results"][0]
    assert top["seek_url"].startswith("https://youtu.be/")
    assert "t=" in top["seek_url"]
    assert data["answer"]


def test_search_no_answer(client):
    r = client.post("/api/search", json={"query": "what is today's weather"})
    assert r.status_code == 200
    data = r.json()
    assert data["refused"] is True
    assert data["intent"] == "no_answer"
    assert data["results"] == []


def test_search_visual_intent(client):
    r = client.post("/api/search", json={"query": "show me the slide with the backlog board"})
    data = r.json()
    assert data["intent"] == "visual"
    assert any(res["modality"] == "visual" for res in data["results"])


def test_admin_login_bad_password(client):
    r = client.post("/api/admin/login", json={"password": "wrong"})
    assert r.status_code == 401


def test_admin_jobs_requires_auth(client):
    r = client.get("/api/admin/jobs")
    assert r.status_code == 401


def test_admin_flow(client):
    r = client.post("/api/admin/login", json={"password": TEST_PASSWORD})
    assert r.status_code == 200
    assert r.json() == {"authenticated": True}

    assert client.get("/api/admin/session").json() == {"authenticated": True}

    jobs = client.get("/api/admin/jobs").json()["jobs"]
    assert len(jobs) >= 2

    r = client.post("/api/admin/ingest", json={"youtube_url": "https://youtu.be/QkdBXUikRQc"})
    assert r.status_code == 200
    job = r.json()["job"]
    assert job["status"] == "queued"
    assert job["video_id"] == "QkdBXUikRQc"

    # the new job is at the top of the list
    assert client.get("/api/admin/jobs").json()["jobs"][0]["id"] == job["id"]


def test_admin_ingest_rejects_invalid_youtube_url(client):
    client.post("/api/admin/login", json={"password": TEST_PASSWORD})

    r = client.post("/api/admin/ingest", json={"youtube_url": "https://example.com/nope"})

    assert r.status_code == 400
    assert "YouTube URL" in r.json()["detail"]
