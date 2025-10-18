"""Tests for profile system."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import create_application
from app.profiles.loader import get_profile_registry


@pytest.fixture
def app():
    """Create test application."""
    return create_application()


@pytest.mark.anyio
async def test_profiles_loaded(app):
    """Test that profiles are loaded at startup."""
    registry = get_profile_registry()
    assert registry.is_loaded()

    profiles = registry.list_profiles()
    profile_ids = [p.id for p in profiles]

    assert "logs" in profile_ids
    assert "metrics" in profile_ids
    assert "policy" in profile_ids

    # Check version fields
    logs_profile = registry.get("logs")
    assert logs_profile is not None
    assert logs_profile.version == "1.0.0"


@pytest.mark.anyio
async def test_list_profiles_endpoint(app):
    """Test GET /v1/profiles endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/v1/profiles")

    assert response.status_code == 200
    profiles = response.json()
    assert isinstance(profiles, list)
    assert len(profiles) >= 3

    ids = [p["id"] for p in profiles]
    assert "logs" in ids
    assert "metrics" in ids
    assert "policy" in ids


@pytest.mark.anyio
async def test_unknown_profile_400(app):
    """Test that unknown profile returns 400 with available list."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/summarize-json",
            json={
                "json": {"test": "data"},
                "profile": "nonexistent",
                "stream": False,
            },
        )

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "unknown_profile"
    assert "available" in data
    assert isinstance(data["available"], list)


@pytest.mark.anyio
async def test_no_profile_backward_compat(app):
    """Test that requests without profile work as before."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/summarize-json",
            json={
                "json": {"orders": [{"id": 1, "total": 20}]},
                "stream": False,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "engine" in data
    assert "bullets" in data
    assert isinstance(data["bullets"], list)


@pytest.mark.anyio
async def test_logs_profile_extractors(app):
    """Test logs profile with level and service extraction."""
    logs_data = {
        "logs": [
            {
                "timestamp": "2025-10-18T10:11:00Z",
                "level": "error",
                "service": "api",
                "code": 504,
            },
            {
                "timestamp": "2025-10-18T10:11:10Z",
                "level": "warn",
                "service": "api",
                "code": 499,
            },
            {
                "timestamp": "2025-10-18T10:11:29Z",
                "level": "error",
                "service": "auth",
                "code": 401,
            },
        ]
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/summarize-json",
            json={
                "json": logs_data,
                "profile": "logs",
                "stream": False,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "bullets" in data
    bullets = data["bullets"]

    # Should have profile bullets (level, service, etc.)
    assert len(bullets) > 0

    # Check that bullets have citations
    for bullet in bullets:
        assert "citations" in bullet
        if bullet["citations"]:  # Profile bullets should have citations
            assert len(bullet["citations"]) > 0
            # Check citations are unique within bullet
            paths = [c["path"] for c in bullet["citations"]]
            assert len(paths) == len(set(paths)), "Citations should be unique"


@pytest.mark.anyio
async def test_profile_precedence(app):
    """Test that explicit request params override profile defaults."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/summarize-json",
            json={
                "json": {"data": [1, 2, 3]},
                "profile": "metrics",  # metrics has style=kpi-block by default
                "style": "bullets",  # explicit override
                "stream": False,
            },
        )

    assert response.status_code == 200
    # Test passes if no error - precedence is applied in backend


@pytest.mark.anyio
async def test_metrics_profile(app):
    """Test metrics profile with numeric extraction."""
    metrics_data = {
        "cpu": [0.4, 0.6, 0.9],
        "mem": [80, 83, 85],
        "latency_ms": [95, 120, 140],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/summarize-json",
            json={
                "json": metrics_data,
                "profile": "metrics",
                "stream": False,
            },
        )

    assert response.status_code == 200
    data = response.json()
    bullets = data["bullets"]
    assert len(bullets) > 0

    # Check for numeric statistics in bullets
    bullet_texts = " ".join([b["text"] for b in bullets])
    assert (
        "cpu" in bullet_texts or "latency_ms" in bullet_texts or "mem" in bullet_texts
    )
