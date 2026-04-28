"""Tests for the /health endpoint."""

from fastapi.testclient import TestClient


def test_health_returns_ok_no_auth(client_no_auth: TestClient) -> None:
    response = client_no_auth.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_health_exempt_from_bearer_token(client_with_auth: TestClient) -> None:
    """Even with APP_TOKEN set, /health needs no Authorization header.

    Azure App Service liveness probes can't send custom headers, so this
    must always be reachable.
    """
    response = client_with_auth.get("/health")
    assert response.status_code == 200
