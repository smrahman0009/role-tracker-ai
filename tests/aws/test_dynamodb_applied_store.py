"""Tests for DynamoDBAppliedStore — same Protocol as FileAppliedStore."""

import pytest

from role_tracker.applied.store import ApplicationRecord
from role_tracker.aws.dynamodb_applied_store import DynamoDBAppliedStore
from tests.aws.conftest import make_table

TABLE_NAME = "role-tracker-applied"
SK = "job_id"


@pytest.fixture
def store(dynamodb_resource: object) -> DynamoDBAppliedStore:
    make_table(dynamodb_resource, TABLE_NAME, SK)
    return DynamoDBAppliedStore(
        TABLE_NAME, dynamodb_resource=dynamodb_resource
    )


def test_empty_store_returns_nothing(store: DynamoDBAppliedStore) -> None:
    assert store.list_applied("alice") == {}
    assert store.is_applied("alice", "j1") is False
    assert store.get_application("alice", "j1") is None


def test_mark_applied_returns_true_first_time(
    store: DynamoDBAppliedStore,
) -> None:
    assert store.mark_applied("alice", "j1") is True
    assert store.mark_applied("alice", "j1") is False  # already there


def test_mark_records_metadata(store: DynamoDBAppliedStore) -> None:
    store.mark_applied(
        "alice",
        "j1",
        resume_filename="resume_v3.pdf",
        resume_sha256="abc123",
        letter_version_used=2,
    )
    rec = store.get_application("alice", "j1")
    assert rec is not None
    assert rec.resume_filename == "resume_v3.pdf"
    assert rec.resume_sha256 == "abc123"
    assert rec.letter_version_used == 2
    assert rec.applied_at is not None


def test_list_applied_returns_dict_keyed_by_job(
    store: DynamoDBAppliedStore,
) -> None:
    store.mark_applied("alice", "j1")
    store.mark_applied("alice", "j2")
    listed = store.list_applied("alice")
    assert set(listed.keys()) == {"j1", "j2"}
    assert all(isinstance(r, ApplicationRecord) for r in listed.values())


def test_per_user_isolation(store: DynamoDBAppliedStore) -> None:
    store.mark_applied("alice", "j1")
    store.mark_applied("bob", "j2")
    assert "j1" not in store.list_applied("bob")
    assert "j2" not in store.list_applied("alice")


def test_unmark_returns_true_when_present(
    store: DynamoDBAppliedStore,
) -> None:
    store.mark_applied("alice", "j1")
    assert store.unmark_applied("alice", "j1") is True
    assert store.is_applied("alice", "j1") is False


def test_unmark_returns_false_when_absent(
    store: DynamoDBAppliedStore,
) -> None:
    assert store.unmark_applied("alice", "ghost") is False


def test_mark_re_apply_overwrites_metadata(
    store: DynamoDBAppliedStore,
) -> None:
    """Marking the same job twice should refresh the metadata."""
    store.mark_applied("alice", "j1", resume_filename="old.pdf")
    store.mark_applied("alice", "j1", resume_filename="new.pdf")
    rec = store.get_application("alice", "j1")
    assert rec is not None
    assert rec.resume_filename == "new.pdf"
