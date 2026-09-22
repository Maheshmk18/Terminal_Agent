import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_fails_without_api_key(client):
    app = create_app()
    app.dependency_overrides = {}
    get_settings.cache_clear()

    response = client.get("/ready")
    body = response.json()

    key_check = next(c for c in body["checks"] if c["name"] == "groq_api_key")
    assert key_check["passed"] is False
    assert response.status_code == 503


def test_ready_passes_with_api_key(monkeypatch, client):
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.api.routes.health.get_settings",
        lambda: Settings(_env_file=None, GROQ_API_KEY="gsk_test"),
    )

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["ready"] is True
