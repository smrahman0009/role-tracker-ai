"""Tests for the Profile + Hidden Lists endpoints."""

from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent

import pytest
from fastapi.testclient import TestClient

from role_tracker.api.main import create_app
from role_tracker.api.routes.profile import get_profile_store
from role_tracker.users.yaml_store import YamlUserProfileStore


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    monkeypatch.delenv("APP_TOKEN", raising=False)

    users_dir = tmp_path / "users"
    users_dir.mkdir()
    (users_dir / "alice.yaml").write_text(
        dedent(
            """
            id: alice
            name: Alice Example
            email: alice@example.com
            phone: 555-1111
            city: Toronto, ON
            linkedin_url: https://linkedin.com/in/alice
            github_url: ""
            portfolio_url: ""
            resume_path: data/resumes/alice.pdf
            queries:
              - what: data scientist
                where: canada
            exclude_companies:
              - bank
              - insurance
            exclude_title_keywords:
              - banking
            exclude_publishers:
              - Foo
              - Bar
            """
        ).strip()
        + "\n"
    )

    app = create_app()
    app.dependency_overrides[get_profile_store] = lambda: YamlUserProfileStore(
        root=users_dir
    )

    with TestClient(app) as c:
        yield c


# ----- GET /profile -----


def test_get_profile_returns_fields_and_flags(client: TestClient) -> None:
    response = client.get("/users/alice/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alice Example"
    assert body["phone"] == "555-1111"
    assert body["linkedin_url"].startswith("https://linkedin.com/")
    # Show flags default to True
    assert body["show_phone_in_header"] is True
    assert body["show_email_in_header"] is True
    assert body["show_portfolio_in_header"] is True


def test_get_profile_404_for_missing_user(client: TestClient) -> None:
    response = client.get("/users/nobody/profile")
    assert response.status_code == 404


# ----- PUT /profile -----


def test_update_profile_patches_only_provided_fields(client: TestClient) -> None:
    response = client.put(
        "/users/alice/profile",
        json={
            "city": "Halifax, NS",
            "show_phone_in_header": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["city"] == "Halifax, NS"           # patched
    assert body["phone"] == "555-1111"              # unchanged
    assert body["show_phone_in_header"] is False    # patched
    assert body["show_email_in_header"] is True     # unchanged


def test_update_profile_persists_across_requests(client: TestClient) -> None:
    client.put(
        "/users/alice/profile",
        json={"portfolio_url": "https://alice.dev"},
    )
    response = client.get("/users/alice/profile")
    assert response.json()["portfolio_url"] == "https://alice.dev"


def test_update_profile_404_for_missing_user(client: TestClient) -> None:
    response = client.put(
        "/users/nobody/profile",
        json={"phone": "anything"},
    )
    assert response.status_code == 404


# ----- GET /hidden -----


def test_get_hidden_lists_returns_all_three(client: TestClient) -> None:
    response = client.get("/users/alice/hidden")
    assert response.status_code == 200
    body = response.json()
    assert "bank" in body["companies"]
    assert "banking" in body["title_keywords"]
    assert "Foo" in body["publishers"]


# ----- PUT /hidden/{kind} -----


def test_replace_hidden_companies(client: TestClient) -> None:
    response = client.put(
        "/users/alice/hidden/companies",
        json={"items": ["consulting", "agency"]},
    )
    assert response.status_code == 200
    assert response.json() == ["consulting", "agency"]
    # And persists
    after = client.get("/users/alice/hidden").json()
    assert after["companies"] == ["consulting", "agency"]


def test_clear_all_via_empty_items(client: TestClient) -> None:
    """Clear-all button = PUT empty items."""
    response = client.put(
        "/users/alice/hidden/publishers", json={"items": []}
    )
    assert response.status_code == 200
    assert response.json() == []
    assert client.get("/users/alice/hidden").json()["publishers"] == []


def test_replace_dedupes_and_strips_whitespace(client: TestClient) -> None:
    response = client.put(
        "/users/alice/hidden/title-keywords",
        json={"items": ["  banking  ", "Banking", "wealth", "wealth"]},
    )
    assert response.status_code == 200
    # First "banking" wins; case-insensitive dedupe drops the second.
    # Whitespace stripped. "wealth" deduped.
    assert response.json() == ["banking", "wealth"]


def test_hidden_404_for_missing_user(client: TestClient) -> None:
    response = client.put(
        "/users/nobody/hidden/companies", json={"items": ["x"]}
    )
    assert response.status_code == 404
