import json

import pytest
from fastapi.testclient import TestClient

import src.main as main_module
from src.models import RoadmapNode, RoadmapResponse


class FakeModel:
    """Stand-in for TextEmbedding / SparseTextEmbedding / TextCrossEncoder
    during app startup (lifespan) - we don't want real ONNX model downloads
    in unit tests."""

    def __init__(self, *args, **kwargs):
        pass


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "TextEmbedding", FakeModel)
    monkeypatch.setattr(main_module, "SparseTextEmbedding", FakeModel)
    monkeypatch.setattr(main_module, "TextCrossEncoder", FakeModel)
    # raise_server_exceptions=False: Starlette's ServerErrorMiddleware always
    # re-raises the original exception after building the handler's response
    # (so a real ASGI server can log it); TestClient mirrors that by default,
    # which would make our "does the 500 handler hide the exception" test
    # fail on the raise instead of asserting on the response body.
    with TestClient(main_module.app, raise_server_exceptions=False) as c:
        yield c


def _fake_roadmap(goal="Learn Python"):
    return RoadmapResponse(
        goal=goal,
        nodes=[RoadmapNode(id="basics", title="Basics", description="desc", prerequisites=[], resources=[])],
    )


# --- health / startup --------------------------------------------------------


def test_health_reflects_models_loaded(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["embedding_model_loaded"] is True
    assert body["status"] == "ok"


def test_health_reports_degraded_when_model_loading_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("model download failed")

    monkeypatch.setattr(main_module, "TextEmbedding", boom)
    monkeypatch.setattr(main_module, "SparseTextEmbedding", FakeModel)
    monkeypatch.setattr(main_module, "TextCrossEncoder", FakeModel)
    with TestClient(main_module.app) as c:
        resp = c.get("/health")
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["embedding_model_loaded"] is False


# --- goal validation ----------------------------------------------------------


def test_generate_roadmap_rejects_too_long_goal(client):
    resp = client.post("/generate-roadmap", json={"goal": "x" * 201})
    assert resp.status_code == 422


def test_generate_roadmap_rejects_control_characters(client):
    resp = client.post("/generate-roadmap", json={"goal": "Learn\x00Python"})
    assert resp.status_code == 422


def test_generate_roadmap_rejects_empty_goal(client):
    resp = client.post("/generate-roadmap", json={"goal": "   "})
    assert resp.status_code == 422


def test_stream_endpoint_rejects_bad_goal(client):
    resp = client.get("/v1/roadmap/stream", params={"goal": "x" * 201})
    assert resp.status_code == 422


# --- success + no-leak error handling -----------------------------------------


def test_generate_roadmap_success(client, monkeypatch):
    async def fake_generate_roadmap(goal, level="beginner", *args, **kwargs):
        return _fake_roadmap(goal)

    monkeypatch.setattr(main_module, "generate_roadmap", fake_generate_roadmap)
    resp = client.post("/generate-roadmap", json={"goal": "Learn Python"})
    assert resp.status_code == 200
    assert resp.json()["goal"] == "Learn Python"


def test_generate_roadmap_does_not_leak_exception_details(client, monkeypatch):
    async def boom(goal, level="beginner", *args, **kwargs):
        raise RuntimeError("internal detail: db password=hunter2")

    monkeypatch.setattr(main_module, "generate_roadmap", boom)
    resp = client.post("/generate-roadmap", json={"goal": "Learn Python"})

    assert resp.status_code == 500
    body = resp.json()
    assert "hunter2" not in json.dumps(body)
    assert "correlation_id" in body and body["correlation_id"]
    assert body["error"] == "Internal server error. Please try again later."


def test_response_has_correlation_id_header(client, monkeypatch):
    async def fake_generate_roadmap(goal, level="beginner", *args, **kwargs):
        return _fake_roadmap(goal)

    monkeypatch.setattr(main_module, "generate_roadmap", fake_generate_roadmap)
    resp = client.post("/generate-roadmap", json={"goal": "Learn Python"})
    assert "X-Correlation-ID" in resp.headers


# --- rate limiting -------------------------------------------------------------


def test_rate_limit_returns_429_with_correlation_id_on_breach(client, monkeypatch):
    async def fake_generate_roadmap(goal, level="beginner", *args, **kwargs):
        return _fake_roadmap(goal)

    monkeypatch.setattr(main_module, "generate_roadmap", fake_generate_roadmap)
    main_module.limiter.reset()

    # Default limit is 5/minute; the 6th request in this window should 429.
    statuses = []
    for _ in range(6):
        resp = client.post("/generate-roadmap", json={"goal": "Learn Python"})
        statuses.append(resp.status_code)

    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429
    breach_body = resp.json()
    assert "correlation_id" in breach_body
    assert "Rate limit exceeded" in breach_body["error"]


# --- CORS ------------------------------------------------------------------


def test_cors_allows_configured_origin_without_credentials_header(client):
    resp = client.options(
        "/generate-roadmap",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-credentials" not in {k.lower() for k in resp.headers.keys()}


def test_cors_rejects_unlisted_origin(client):
    resp = client.options(
        "/generate-roadmap",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers.get("access-control-allow-origin") != "https://evil.example.com"


# --- SSE streaming contract --------------------------------------------------


def test_stream_endpoint_emits_structure_resources_done_in_order(client, monkeypatch):
    main_module.limiter.reset()

    async def fake_stream(goal, level="beginner", *args, **kwargs):
        yield ("structure", {"nodes": [{"id": "a", "title": "A", "description": "d", "prerequisites": []}]})
        yield ("resources", {"id": "a", "resources": []})
        yield ("done", {"cache_hit": False})

    monkeypatch.setattr(main_module, "stream_roadmap_events", fake_stream)
    resp = client.get("/v1/roadmap/stream", params={"goal": "Learn Python"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    text = resp.text
    assert "event: structure" in text
    assert "event: resources" in text
    assert "event: done" in text
    assert text.index("event: structure") < text.index("event: resources") < text.index("event: done")


def test_stream_endpoint_emits_error_event_on_failure(client, monkeypatch):
    main_module.limiter.reset()

    async def fake_stream(goal, level="beginner", *args, **kwargs):
        yield ("structure", {"nodes": []})
        raise RuntimeError("boom: secret detail")

    monkeypatch.setattr(main_module, "stream_roadmap_events", fake_stream)
    resp = client.get("/v1/roadmap/stream", params={"goal": "Learn Python"})

    text = resp.text
    assert "event: error" in text
    assert "secret detail" not in text
    assert "correlation_id" in text
