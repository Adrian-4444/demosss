"""Tests for health and readiness probes, and request tracking."""

from unittest.mock import patch
from starlette.testclient import TestClient


def test_health_root_returns_ok(client: TestClient):
    """Test that GET /health returns 200 with service information and UTC timestamp."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data
    assert "timestamp" in data


def test_health_versioned_returns_ok(client: TestClient):
    """Test that GET /api/v1/health returns 200 with service information."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_readiness_healthy_database(client: TestClient):
    """Test that GET /ready returns 200 and connected status when database is reachable."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert "timestamp" in data


def test_readiness_unhealthy_database(client: TestClient):
    """Test that GET /ready returns 503 and disconnected status when database check fails."""
    with patch("app.routers.health.check_db_connection", return_value=False):
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "disconnected"


def test_request_id_header_generated_and_returned(client: TestClient):
    """Test that request ID is generated and returned in response headers."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


def test_custom_request_id_preserved(client: TestClient):
    """Test that custom X-Request-ID passed by client is preserved in response headers."""
    custom_id = "test-custom-req-id-12345"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id
