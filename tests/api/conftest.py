"""Shared fixtures for API tests."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear env vars that the developer's local .env might define so
    pydantic-settings doesn't pick them up during a test run. Setting
    the var explicitly (even to "") makes the env-var value take
    precedence over anything in .env."""
    monkeypatch.setenv("APP_TOKEN", "")
    monkeypatch.setenv("APP_TOKENS", "")
    monkeypatch.setenv("STORAGE_BACKEND", "file")


def _build_test_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    token: str = "",
    tokens: str = "",
) -> FastAPI:
    """Build a fresh FastAPI app under specific env settings.

    Tests import `create_app` lazily so monkeypatched env vars are applied
    BEFORE Settings() reads them.
    """
    monkeypatch.setenv("APP_TOKEN", token)
    monkeypatch.setenv("APP_TOKENS", tokens)

    from role_tracker.api.main import create_app

    return create_app()


@pytest.fixture
def client_no_auth(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Test client with APP_TOKEN unset — auth bypassed (dev mode)."""
    app = _build_test_app(monkeypatch, token="")
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client_with_auth(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Test client with APP_TOKEN='test-secret' — bearer required."""
    app = _build_test_app(monkeypatch, token="test-secret")

    # Mount a tiny protected route inside the test app so middleware
    # behaviour can be exercised without depending on real endpoints
    # that don't exist yet.
    @app.get("/test/protected")
    def _protected() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        yield client


@pytest.fixture
def client_multi_user(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Test client with two bound tokens: tok-rafin→rafin_, tok-ahasan→ahasan_."""
    app = _build_test_app(
        monkeypatch,
        tokens='{"tok-rafin": "rafin_", "tok-ahasan": "ahasan_"}',
    )

    @app.get("/users/{user_id}/probe")
    def _probe(user_id: str) -> dict[str, str]:
        return {"user_id": user_id}

    with TestClient(app) as client:
        yield client
