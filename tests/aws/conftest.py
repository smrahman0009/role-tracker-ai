"""Shared fixtures for AWS-backend tests.

Every test in tests/aws/ runs inside a moto context — no real AWS
calls happen. Each fixture spins up a fresh in-memory service, yields
a configured boto3 resource, and tears it down between tests so
state never leaks across cases.
"""

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

# A fixed region everywhere — moto cares about consistency, not the
# specific value.
TEST_REGION = "ca-central-1"


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop boto3 from accidentally reading real credentials."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", TEST_REGION)


@pytest.fixture
def dynamodb_resource() -> Iterator[object]:
    """Yield a moto-backed DynamoDB resource."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name=TEST_REGION)


def make_table(
    dynamodb_resource: object,
    table_name: str,
    sort_key_name: str,
) -> object:
    """Create a (user_id, sort_key) DynamoDB table — same shape every
    domain table uses in production. Returns the moto Table object."""
    table = dynamodb_resource.create_table(  # type: ignore[attr-defined]
        TableName=table_name,
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": sort_key_name, "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": sort_key_name, "KeyType": "RANGE"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table
