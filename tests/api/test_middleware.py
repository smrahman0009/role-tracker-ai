"""Tests for the bearer-token middleware."""

from fastapi.testclient import TestClient


def test_protected_route_requires_authorization_header(
    client_with_auth: TestClient,
) -> None:
    response = client_with_auth.get("/test/protected")
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]


def test_protected_route_rejects_wrong_token(client_with_auth: TestClient) -> None:
    response = client_with_auth.get(
        "/test/protected", headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_protected_route_rejects_malformed_header(
    client_with_auth: TestClient,
) -> None:
    # Missing the "Bearer " prefix.
    response = client_with_auth.get(
        "/test/protected", headers={"Authorization": "test-secret"}
    )
    assert response.status_code == 401


def test_protected_route_accepts_correct_token(client_with_auth: TestClient) -> None:
    response = client_with_auth.get(
        "/test/protected", headers={"Authorization": "Bearer test-secret"}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_no_auth_required_when_token_unset(client_no_auth: TestClient) -> None:
    """Empty APP_TOKEN = dev mode = no token check, all routes open."""
    response = client_no_auth.get("/health")
    assert response.status_code == 200


# ----- Multi-user mode (APP_TOKENS) ---------------------------------------


def test_multi_user_token_grants_access_to_bound_user(
    client_multi_user: TestClient,
) -> None:
    response = client_multi_user.get(
        "/users/rafin_/probe", headers={"Authorization": "Bearer tok-rafin"}
    )
    assert response.status_code == 200
    assert response.json() == {"user_id": "rafin_"}


def test_multi_user_token_rejected_for_other_user_id(
    client_multi_user: TestClient,
) -> None:
    """Rafin's token cannot read Ahasan's data."""
    response = client_multi_user.get(
        "/users/ahasan_/probe", headers={"Authorization": "Bearer tok-rafin"}
    )
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


def test_multi_user_unknown_token_returns_401(
    client_multi_user: TestClient,
) -> None:
    response = client_multi_user.get(
        "/users/rafin_/probe", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_multi_user_mode_still_exempts_health(
    client_multi_user: TestClient,
) -> None:
    response = client_multi_user.get("/health")
    assert response.status_code == 200


def test_parse_tokens_rejects_malformed_json() -> None:
    import pytest

    from role_tracker.api.middleware import parse_tokens

    with pytest.raises(Exception):
        parse_tokens("{not json")
    with pytest.raises(ValueError):
        parse_tokens('["array", "not", "object"]')
    with pytest.raises(ValueError):
        parse_tokens('{"tok": ""}')
