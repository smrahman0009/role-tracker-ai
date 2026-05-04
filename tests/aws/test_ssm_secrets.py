"""Tests for the SSM Parameter Store secret loader."""

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from role_tracker.aws.ssm_secrets import load_secrets_into_env

REGION = "ca-central-1"
PREFIX = "/role-tracker"


@pytest.fixture
def ssm_client() -> Iterator[object]:
    with mock_aws():
        client = boto3.client("ssm", region_name=REGION)
        # Seed three SecureStrings — same shape as 04-ssm.sh creates.
        for name, value in [
            ("ANTHROPIC_API_KEY", "anthropic-secret"),
            ("OPENAI_API_KEY", "openai-secret"),
            ("JSEARCH_RAPIDAPI_KEY", "jsearch-secret"),
        ]:
            client.put_parameter(
                Name=f"{PREFIX}/{name}",
                Value=value,
                Type="SecureString",
            )
        yield client


def test_loads_all_params_under_prefix(
    ssm_client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("JSEARCH_RAPIDAPI_KEY", raising=False)

    fetched = load_secrets_into_env(PREFIX, ssm_client=ssm_client)

    assert fetched == {
        "ANTHROPIC_API_KEY": "anthropic-secret",
        "OPENAI_API_KEY": "openai-secret",
        "JSEARCH_RAPIDAPI_KEY": "jsearch-secret",
    }
    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "anthropic-secret"
    assert os.environ["OPENAI_API_KEY"] == "openai-secret"


def test_does_not_overwrite_by_default(
    ssm_client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "preexisting-from-dotenv")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("JSEARCH_RAPIDAPI_KEY", raising=False)

    fetched = load_secrets_into_env(PREFIX, ssm_client=ssm_client)

    # The pre-set env var wins, so it's NOT in fetched.
    assert "ANTHROPIC_API_KEY" not in fetched
    # The others were unset, so SSM populates them.
    assert fetched["OPENAI_API_KEY"] == "openai-secret"

    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "preexisting-from-dotenv"


def test_overwrite_true_replaces_existing(
    ssm_client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "old")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("JSEARCH_RAPIDAPI_KEY", raising=False)

    load_secrets_into_env(PREFIX, ssm_client=ssm_client, overwrite=True)

    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "anthropic-secret"


def test_handles_pagination(
    ssm_client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seed > MaxResults parameters and verify all of them load."""
    for i in range(15):
        ssm_client.put_parameter(  # type: ignore[attr-defined]
            Name=f"{PREFIX}/EXTRA_{i}",
            Value=f"value-{i}",
            Type="SecureString",
        )
        monkeypatch.delenv(f"EXTRA_{i}", raising=False)

    fetched = load_secrets_into_env(PREFIX, ssm_client=ssm_client)
    extras = {k: v for k, v in fetched.items() if k.startswith("EXTRA_")}
    assert len(extras) == 15
