"""Tests for GET /users/{user_id}/usage."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from role_tracker.api.main import create_app
from role_tracker.api.routes.jobs import get_usage_store
from role_tracker.usage import FileUsageStore


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[tuple[TestClient, FileUsageStore]]:
    monkeypatch.delenv("APP_TOKEN", raising=False)
    app = create_app()
    store = FileUsageStore(root=tmp_path / "usage")
    app.dependency_overrides[get_usage_store] = lambda: store
    with TestClient(app) as c:
        yield c, store


def test_returns_zero_month_when_no_usage(
    client: tuple[TestClient, FileUsageStore],
) -> None:
    c, _ = client
    r = c.get("/users/alice/usage")
    assert r.status_code == 200
    body = r.json()
    assert body["current"]["jsearch_calls"] == 0
    assert body["current"]["feature_calls"] == []
    assert body["current"]["estimated_total_cost_usd"] == 0.0
    assert body["history"] == []


def test_reflects_recorded_calls(
    client: tuple[TestClient, FileUsageStore],
) -> None:
    c, store = client
    store.record_jsearch("alice")
    store.record_feature("alice", "cover_letter_generate")
    store.record_feature("alice", "embedding")
    store.record_feature("alice", "embedding")

    r = c.get("/users/alice/usage")
    body = r.json()

    assert body["current"]["jsearch_calls"] == 1
    features = {f["feature"]: f for f in body["current"]["feature_calls"]}
    assert features["cover_letter_generate"]["count"] == 1
    assert features["embedding"]["count"] == 2
    # Anthropic features are sorted before OpenAI.
    assert body["current"]["feature_calls"][0]["feature"] == "cover_letter_generate"
    assert body["current"]["estimated_anthropic_cost_usd"] == pytest.approx(0.05)
    assert body["current"]["estimated_openai_cost_usd"] == pytest.approx(0.001)
