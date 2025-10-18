import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_application


@pytest.fixture(scope="module")
def test_app():
    return create_application()


@pytest.mark.anyio
async def test_summarize_endpoint_returns_bullets(test_app):
    payload = {
        "json": {
            "orders": [
                {"id": 1, "total": 20, "status": "paid"},
                {"id": 2, "total": 40, "status": "paid"},
                {"id": 3, "total": 5, "status": "failed"},
            ]
        },
        "stream": False,
    }
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
        response = await client.post("/v1/summarize-json", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "deterministic"
    assert len(body["bullets"]) >= 1
    for bullet in body["bullets"]:
        assert bullet["citations"]
        for citation in bullet["citations"]:
            previews = citation["value_preview"]
            assert isinstance(previews, list) and 1 <= len(previews) <= 3
            typed_preview = citation["value_preview_typed"]
            assert isinstance(typed_preview, list)
    stats = body["evidence_stats"]
    assert {"paths_count", "bytes_examined", "elapsed_ms"} <= set(stats.keys())
    assert stats["paths_count"] >= 1


@pytest.mark.anyio
async def test_streaming_format_emits_phase_objects(test_app):
    payload = {
        "json": {
            "metrics": [{"value": 1}, {"value": 2}, {"value": 3}],
        }
    }
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
        async with client.stream(
            "POST", "/v1/summarize-json", json=payload
        ) as response:
            assert response.status_code == 200
            events = []
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                events.append(json.loads(line[len("data: ") :]))
    assert events, "Expected SSE events"
    for event in events[:-1]:
        assert event["phase"] == "summary"
        assert "bullet" in event
        for citation in event["bullet"]["citations"]:
            previews = citation["value_preview"]
            assert isinstance(previews, list) and 1 <= len(previews) <= 3
            assert isinstance(citation["value_preview_typed"], list)
            typed_preview = citation["value_preview_typed"]
            assert isinstance(typed_preview, list)
    final_event = events[-1]
    assert final_event["phase"] == "complete"
    assert "evidence_stats" in final_event


@pytest.mark.anyio
async def test_payload_too_large_error_structured(test_app):
    settings = get_settings()
    original_limit = settings.max_payload_bytes
    settings.max_payload_bytes = 10
    try:
        payload = {"json": {"blob": "x" * 64}}
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
            response = await client.post("/v1/summarize-json", json=payload)
        assert response.status_code == 413
        body = response.json()
        assert body["error"] == "payload_too_large"
        assert body["limit_bytes"] == 10
    finally:
        settings.max_payload_bytes = original_limit


@pytest.mark.anyio
async def test_depth_limit_error_structured(test_app):
    settings = get_settings()
    original_depth = settings.max_json_depth
    settings.max_json_depth = 2
    try:
        payload = {"json": {"a": {"b": {"c": 1}}}}
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
            response = await client.post("/v1/summarize-json", json=payload)
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "depth_limit"
        assert body["limit"] == 2
    finally:
        settings.max_json_depth = original_depth


@pytest.mark.anyio
async def test_chat_endpoint_focuses_on_last_user_message(test_app):
    payload = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Summarize payments."},
        ],
        "json": {
            "payments": [
                {"amount": 10, "status": "completed"},
                {"amount": 5, "status": "failed"},
            ],
        },
    }
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "deterministic"
    assert "- payments" in body["reply"].lower()
    assert "evidence_stats" in body
    assert body["evidence_stats"]["paths_count"] >= 1


@pytest.mark.anyio
async def test_invalid_json_body_structured(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
        response = await client.post(
            "/v1/summarize-json",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400
    body = response.json()
    assert body["error"] in {"invalid_json", "validation_error"}


@pytest.mark.anyio
async def test_healthz_endpoint(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["engine"] == "deterministic"
    assert body["version"]
    assert body["max_payload_bytes"] == get_settings().max_payload_bytes
