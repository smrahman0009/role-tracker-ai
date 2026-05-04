"""Tests for the saved-queries API routes.

These exercise the route handlers + Pydantic validation + dependency
injection — using a tmp-path-rooted JsonQueryStore so no real files get
touched.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from role_tracker.api.main import create_app
from role_tracker.api.routes.queries import get_query_store
from role_tracker.queries.json_store import JsonQueryStore


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    """Test client with auth disabled and the query store rooted in tmp_path."""

    app = create_app()
    test_store = JsonQueryStore(
        root=tmp_path / "queries",
        bootstrap_yaml_root=tmp_path / "users",
    )
    app.dependency_overrides[get_query_store] = lambda: test_store

    with TestClient(app) as c:
        yield c


def test_list_queries_empty(client: TestClient) -> None:
    response = client.get("/users/alice/queries")
    assert response.status_code == 200
    body = response.json()
    assert body["queries"] == []
    assert body["next_refresh_allowed_at"] is None


def test_create_query_returns_201(client: TestClient) -> None:
    response = client.post(
        "/users/alice/queries",
        json={"what": "data scientist", "where": "canada"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["what"] == "data scientist"
    assert body["where"] == "canada"
    assert body["enabled"] is True
    assert "query_id" in body
    assert "created_at" in body


def test_create_then_list_round_trip(client: TestClient) -> None:
    client.post(
        "/users/alice/queries",
        json={"what": "data scientist", "where": "canada"},
    )
    client.post(
        "/users/alice/queries",
        json={"what": "ML engineer", "where": "toronto"},
    )

    response = client.get("/users/alice/queries")
    body = response.json()
    assert len(body["queries"]) == 2
    expected = {"data scientist", "ML engineer"}
    assert {q["what"] for q in body["queries"]} == expected


def test_create_query_validates_empty_strings(client: TestClient) -> None:
    response = client.post(
        "/users/alice/queries", json={"what": "", "where": "canada"}
    )
    assert response.status_code == 422  # Pydantic validation error


def test_create_query_requires_both_fields(client: TestClient) -> None:
    response = client.post("/users/alice/queries", json={"what": "data scientist"})
    assert response.status_code == 422


def test_update_query_partial(client: TestClient) -> None:
    create_response = client.post(
        "/users/alice/queries",
        json={"what": "data scientist", "where": "canada"},
    )
    query_id = create_response.json()["query_id"]

    update_response = client.put(
        f"/users/alice/queries/{query_id}", json={"where": "toronto"}
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["what"] == "data scientist"  # unchanged
    assert body["where"] == "toronto"        # patched


def test_update_query_can_disable(client: TestClient) -> None:
    create_response = client.post(
        "/users/alice/queries", json={"what": "x", "where": "y"}
    )
    query_id = create_response.json()["query_id"]

    update_response = client.put(
        f"/users/alice/queries/{query_id}", json={"enabled": False}
    )
    assert update_response.status_code == 200
    assert update_response.json()["enabled"] is False


def test_update_query_404_when_missing(client: TestClient) -> None:
    response = client.put(
        "/users/alice/queries/nonexistent", json={"where": "toronto"}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_query(client: TestClient) -> None:
    create_response = client.post(
        "/users/alice/queries", json={"what": "x", "where": "y"}
    )
    query_id = create_response.json()["query_id"]

    delete_response = client.delete(f"/users/alice/queries/{query_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/users/alice/queries")
    assert list_response.json()["queries"] == []


def test_delete_query_404_when_missing(client: TestClient) -> None:
    response = client.delete("/users/alice/queries/nonexistent")
    assert response.status_code == 404


def test_users_are_isolated(client: TestClient) -> None:
    client.post("/users/alice/queries", json={"what": "ml", "where": "canada"})
    client.post("/users/bob/queries", json={"what": "data", "where": "toronto"})

    alice = client.get("/users/alice/queries").json()["queries"]
    bob = client.get("/users/bob/queries").json()["queries"]
    assert len(alice) == 1
    assert len(bob) == 1
    assert alice[0]["what"] == "ml"
    assert bob[0]["what"] == "data"
