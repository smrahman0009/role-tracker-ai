"""Tests for DynamoDBQueryStore — same Protocol as JsonQueryStore."""

import pytest

from role_tracker.aws.dynamodb_query_store import DynamoDBQueryStore
from role_tracker.queries.models import SavedQuery
from tests.aws.conftest import make_table

TABLE_NAME = "role-tracker-queries"
SK = "query_id"


@pytest.fixture
def store(dynamodb_resource: object) -> DynamoDBQueryStore:
    make_table(dynamodb_resource, TABLE_NAME, SK)
    return DynamoDBQueryStore(
        TABLE_NAME, dynamodb_resource=dynamodb_resource
    )


def test_list_returns_empty_for_new_user(store: DynamoDBQueryStore) -> None:
    assert store.list_queries("alice") == []


def test_add_then_list(store: DynamoDBQueryStore) -> None:
    q = store.add_query("alice", "data scientist", "toronto")
    assert isinstance(q, SavedQuery)
    assert q.what == "data scientist"
    assert q.where == "toronto"
    assert q.enabled is True

    [listed] = store.list_queries("alice")
    assert listed.query_id == q.query_id


def test_creation_order_preserved(store: DynamoDBQueryStore) -> None:
    q1 = store.add_query("alice", "first", "canada")
    q2 = store.add_query("alice", "second", "canada")
    q3 = store.add_query("alice", "third", "canada")
    ids = [q.query_id for q in store.list_queries("alice")]
    assert ids == [q1.query_id, q2.query_id, q3.query_id]


def test_per_user_isolation(store: DynamoDBQueryStore) -> None:
    store.add_query("alice", "a", "x")
    store.add_query("bob", "b", "y")
    assert len(store.list_queries("alice")) == 1
    assert len(store.list_queries("bob")) == 1


def test_get_query_hit_and_miss(store: DynamoDBQueryStore) -> None:
    q = store.add_query("alice", "what", "where")
    assert store.get_query("alice", q.query_id) is not None
    assert store.get_query("alice", "nonexistent") is None


def test_update_partial_fields(store: DynamoDBQueryStore) -> None:
    q = store.add_query("alice", "data scientist", "canada")
    updated = store.update_query(
        "alice", q.query_id, what="ml engineer", enabled=False
    )
    assert updated is not None
    assert updated.what == "ml engineer"
    assert updated.where == "canada"  # untouched
    assert updated.enabled is False


def test_update_with_no_fields_returns_existing(
    store: DynamoDBQueryStore,
) -> None:
    q = store.add_query("alice", "what", "where")
    result = store.update_query("alice", q.query_id)
    assert result is not None
    assert result.query_id == q.query_id


def test_update_missing_returns_none(store: DynamoDBQueryStore) -> None:
    assert store.update_query("alice", "nonexistent", what="x") is None


def test_delete_existing_returns_true(store: DynamoDBQueryStore) -> None:
    q = store.add_query("alice", "what", "where")
    assert store.delete_query("alice", q.query_id) is True
    assert store.list_queries("alice") == []


def test_delete_missing_returns_false(store: DynamoDBQueryStore) -> None:
    assert store.delete_query("alice", "nope") is False
