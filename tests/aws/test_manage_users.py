"""Tests for the user-management CLI (infra/users/manage_users.py).

All tests run inside a moto SSM context, so the script never touches
real AWS. We import the module by file path because it lives outside
the package tree (intentionally — it's an ops tool, not library code).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import boto3
import pytest
from moto import mock_aws

REGION = "ca-central-1"
PARAM = "/role-tracker/APP_TOKENS"

_MODULE_PATH = (
    Path(__file__).parent.parent.parent / "infra" / "users" / "manage_users.py"
)


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("manage_users", _MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["manage_users"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def manage_users() -> Any:
    return _load_module()


@pytest.fixture
def ssm() -> Any:
    with mock_aws():
        yield boto3.client("ssm", region_name=REGION)


def _get(ssm: Any) -> dict[str, str]:
    val = ssm.get_parameter(Name=PARAM, WithDecryption=True)["Parameter"]["Value"]
    return json.loads(val)


def test_add_creates_param_and_prints_token(
    manage_users: Any, ssm: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = manage_users.main(["--region", REGION, "add", "rafin_"])
    assert rc == 0
    tokens = _get(ssm)
    assert list(tokens.values()) == ["rafin_"]
    [token] = tokens.keys()
    assert len(token) >= 30  # url-safe 32 bytes is ~43 chars
    captured = capsys.readouterr().out
    assert token in captured
    assert "rafin_" in captured


def test_add_rejects_duplicate_user(
    manage_users: Any, ssm: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    manage_users.main(["--region", REGION, "add", "rafin_"])
    rc = manage_users.main(["--region", REGION, "add", "rafin_"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "already" in err.lower()
    # Map should still have exactly one token for rafin_.
    assert list(_get(ssm).values()) == ["rafin_"]


def test_rotate_replaces_token(manage_users: Any, ssm: Any) -> None:
    manage_users.main(["--region", REGION, "add", "rafin_"])
    [old_token] = _get(ssm).keys()
    rc = manage_users.main(["--region", REGION, "rotate", "rafin_"])
    assert rc == 0
    new_tokens = _get(ssm)
    assert old_token not in new_tokens
    assert list(new_tokens.values()) == ["rafin_"]


def test_rotate_fails_for_unknown_user(
    manage_users: Any, ssm: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = manage_users.main(["--region", REGION, "rotate", "ghost"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_remove_drops_token(manage_users: Any, ssm: Any) -> None:
    manage_users.main(["--region", REGION, "add", "rafin_"])
    manage_users.main(["--region", REGION, "add", "ahasan_"])
    rc = manage_users.main(["--region", REGION, "remove", "rafin_"])
    assert rc == 0
    remaining = _get(ssm)
    assert list(remaining.values()) == ["ahasan_"]


def test_list_shows_users(
    manage_users: Any, ssm: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    manage_users.main(["--region", REGION, "add", "rafin_"])
    manage_users.main(["--region", REGION, "add", "ahasan_"])
    capsys.readouterr()  # flush
    rc = manage_users.main(["--region", REGION, "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "rafin_" in out
    assert "ahasan_" in out


def test_list_when_param_missing(
    manage_users: Any, ssm: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = manage_users.main(["--region", REGION, "list"])
    assert rc == 0
    assert "no users" in capsys.readouterr().out.lower()
