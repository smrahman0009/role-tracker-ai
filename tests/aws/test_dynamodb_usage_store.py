"""Tests for DynamoDBUsageStore — same behaviour as FileUsageStore."""

from datetime import UTC, datetime

import pytest

from role_tracker.aws.dynamodb_usage_store import (
    DynamoDBUsageStore,
    _current_year_month,
)
from role_tracker.usage.store import MonthlyUsage
from tests.aws.conftest import make_table

TABLE_NAME = "role-tracker-usage"
SK = "year_month"


@pytest.fixture
def store(dynamodb_resource: object) -> DynamoDBUsageStore:
    make_table(dynamodb_resource, TABLE_NAME, SK)
    return DynamoDBUsageStore(
        TABLE_NAME, dynamodb_resource=dynamodb_resource
    )


def test_get_month_returns_zero_record_when_missing(
    store: DynamoDBUsageStore,
) -> None:
    m = store.get_month("alice", "1999-01")
    assert isinstance(m, MonthlyUsage)
    assert m.jsearch_calls == 0
    assert m.feature_calls == {}


def test_record_jsearch_increments_atomically(
    store: DynamoDBUsageStore,
) -> None:
    for _ in range(3):
        store.record_jsearch("alice")
    [m] = store.list_months("alice")
    assert m.jsearch_calls == 3


def test_record_feature_per_user_isolation(
    store: DynamoDBUsageStore,
) -> None:
    store.record_feature("alice", "embedding")
    store.record_feature("bob", "cover_letter_polish")
    [a] = store.list_months("alice")
    [b] = store.list_months("bob")
    assert a.feature_calls == {"embedding": 1}
    assert b.feature_calls == {"cover_letter_polish": 1}


def test_estimated_costs_match_file_store(
    store: DynamoDBUsageStore,
) -> None:
    # Same scenario as the FileUsageStore test — proves the cost
    # math is unaffected by the storage swap.
    for _ in range(2):
        store.record_feature("alice", "cover_letter_generate")
    for _ in range(4):
        store.record_feature("alice", "embedding")
    store.record_feature("alice", "cover_letter_polish")

    [m] = store.list_months("alice")
    assert m.estimated_anthropic_cost_usd == pytest.approx(0.105)
    assert m.estimated_openai_cost_usd == pytest.approx(0.002)
    assert m.estimated_total_cost_usd == pytest.approx(0.107)


def test_list_months_returns_newest_first(
    store: DynamoDBUsageStore,
    dynamodb_resource: object,
) -> None:
    table = dynamodb_resource.Table(TABLE_NAME)  # type: ignore[attr-defined]
    # Pre-seed three months so we don't depend on the clock.
    for ym, count in [("2026-01", 1), ("2026-03", 3), ("2026-02", 2)]:
        table.put_item(
            Item={
                "user_id": "alice",
                "year_month": ym,
                "jsearch_calls": count,
            }
        )
    months = store.list_months("alice")
    assert [m.year_month for m in months] == ["2026-03", "2026-02", "2026-01"]
    assert [m.jsearch_calls for m in months] == [3, 2, 1]


def test_get_month_reads_specific_month(
    store: DynamoDBUsageStore,
    dynamodb_resource: object,
) -> None:
    table = dynamodb_resource.Table(TABLE_NAME)  # type: ignore[attr-defined]
    table.put_item(
        Item={
            "user_id": "alice",
            "year_month": "2026-04",
            "jsearch_calls": 5,
            "f_embedding": 7,
        }
    )
    m = store.get_month("alice", "2026-04")
    assert m.year_month == "2026-04"
    assert m.jsearch_calls == 5
    assert m.feature_calls == {"embedding": 7}


def test_record_writes_to_current_month(
    store: DynamoDBUsageStore,
) -> None:
    """record_* should land in the *current* year_month, regardless
    of what other months exist in the table."""
    expected_ym = _current_year_month()
    store.record_jsearch("alice")
    months = store.list_months("alice")
    assert len(months) == 1
    assert months[0].year_month == expected_ym


def test_current_year_month_format() -> None:
    """Sanity-check the format helper. Should be 'YYYY-MM'."""
    ym = _current_year_month()
    assert len(ym) == 7
    assert ym[4] == "-"
    year, month = ym.split("-")
    now = datetime.now(UTC)
    assert int(year) == now.year
    assert int(month) == now.month
