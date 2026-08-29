"""Endpoint coverage for the public API."""

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
    expected_ids = {
        "QkdBXUikRQc",
        "DVtcZQ2QdBg",
        "as9IYFrTiKc",
        "u4ZoJKF_VuA",
        "1Gdl-A1DvpA",
        "iCvmsMzlF7o",
        "TGdLss5Srnk",
        "E76CUtSHMrU",
        "h6fcK_fRYaI",
        "v7AYKMP6rOE",
        "Th8JoIan4dg",
        "arj7oStGLkU",
        "uxPdPpi5W4o",
    }
    assert len(data) == 13
    assert {v["id"] for v in data} == expected_ids
    assert all(v["thumbnail_url"].startswith("https://") for v in data)
    assert {v["id"] for v in data if v["indexed"]} == expected_ids
    assert next(v for v in data if v["id"] == "Th8JoIan4dg")["artifact_stats"] == {
        "transcript_segments": 544,
        "transcript_chunks": 80,
        "visual_frames": 20,
        "indexed_vectors": 100,
        "frame_interval_seconds": 10,
    }


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


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    import json

    frames: list[tuple[str, dict]] = []
    for block in body.split("\n\n"):
        event = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if not data_lines:
            continue
        raw = "\n".join(data_lines)
        frames.append((event, json.loads(raw) if raw else {}))
    return frames


def test_search_stream_answerable(client):
    with client.stream(
        "POST", "/api/search/stream", json={"query": "how to negotiate salary"}
    ) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        body = "".join(r.iter_text())

    frames = _parse_sse(body)
    names = [event for event, _ in frames]
    assert "node" in names
    assert "final" in names
    assert names[-1] == "done"
    nodes = [payload["node"] for event, payload in frames if event == "node"]
    assert "retrieve_transcript" in nodes
    assert "retrieve_visual" in nodes
    assert "fuse_results" in nodes
    final = next(payload for event, payload in frames if event == "final")
    assert final["refused"] is False
    assert final["results"]
    assert final["answer"]


def test_search_stream_weather_refuses(client):
    with client.stream(
        "POST", "/api/search/stream", json={"query": "what is today's weather"}
    ) as r:
        body = "".join(r.iter_text())

    frames = _parse_sse(body)
    gate = [
        payload
        for event, payload in frames
        if event == "node"
        and payload["node"] == "apply_retrieval_gate"
        and payload["status"] != "started"
    ]
    assert gate[-1]["status"] == "refused"
    final = next(payload for event, payload in frames if event == "final")
    assert final["refused"] is True
    assert final["intent"] == "no_answer"
    assert final["results"] == []


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
    assert job["stage"] == "queued"
    assert job["stages_seen"] == ["queued"]

    # the new job is at the top of the list
    assert client.get("/api/admin/jobs").json()["jobs"][0]["id"] == job["id"]


def test_admin_ingest_rejects_invalid_youtube_url(client):
    client.post("/api/admin/login", json={"password": TEST_PASSWORD})

    r = client.post("/api/admin/ingest", json={"youtube_url": "https://example.com/nope"})

    assert r.status_code == 400
    assert "YouTube URL" in r.json()["detail"]


def test_serializer_refuses_empty_secret_in_deployed_mode(monkeypatch):
    """In deployed mode (Secrets Manager configured), an empty SESSION_SECRET must
    raise — never silently fall back to the dev default that would let an attacker
    forge admin cookies."""
    from api import auth

    monkeypatch.setattr(settings, "session_secret", "")
    monkeypatch.setattr(settings, "secrets_manager_secret_name", "video-rag/runtime")

    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        auth._serializer()


def test_serializer_allows_dev_fallback_outside_deployed_mode(monkeypatch):
    """Local dev without Secrets Manager keeps the convenience fallback."""
    from api import auth

    monkeypatch.setattr(settings, "session_secret", "")
    monkeypatch.setattr(settings, "secrets_manager_secret_name", "")

    serializer = auth._serializer()
    # Round-trip a token to confirm a usable serializer was returned.
    token = serializer.dumps({"role": "admin"})
    assert serializer.loads(token) == {"role": "admin"}


def test_lambda_handler_flushes_traces_even_on_error(monkeypatch):
    """Lambda freezes the moment the handler returns — pending LangSmith
    batches must be drained inside the invocation, success or failure."""
    from api import main

    flushes: list[bool] = []
    monkeypatch.setattr(main, "_flush_langsmith_traces", lambda: flushes.append(True))

    monkeypatch.setattr(main, "_mangum", lambda event, context: {"statusCode": 200})
    assert main.handler({}, None) == {"statusCode": 200}
    assert flushes == [True]

    def broken(event, context):
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "_mangum", broken)
    with pytest.raises(RuntimeError):
        main.handler({}, None)
    assert flushes == [True, True]


def test_langsmith_flush_noops_without_tracing_config(monkeypatch):
    from api import main

    monkeypatch.setattr(settings, "langsmith_tracing", True)
    monkeypatch.setattr(settings, "langsmith_api_key", "")
    main._flush_langsmith_traces()  # must not raise or import tracer machinery
