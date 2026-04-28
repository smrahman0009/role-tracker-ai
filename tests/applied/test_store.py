"""Tests for the FileAppliedStore."""

from pathlib import Path

import pytest

from role_tracker.applied.store import FileAppliedStore


@pytest.fixture
def store(tmp_path: Path) -> FileAppliedStore:
    return FileAppliedStore(root=tmp_path / "applied")


def test_initially_empty(store: FileAppliedStore) -> None:
    assert store.list_applied("alice") == set()
    assert store.is_applied("alice", "job_a") is False


def test_mark_applied_returns_true_first_time(
    store: FileAppliedStore,
) -> None:
    assert store.mark_applied("alice", "job_a") is True
    assert store.is_applied("alice", "job_a") is True


def test_mark_applied_returns_false_when_already_applied(
    store: FileAppliedStore,
) -> None:
    store.mark_applied("alice", "job_a")
    assert store.mark_applied("alice", "job_a") is False


def test_unmark_applied_returns_true_when_present(
    store: FileAppliedStore,
) -> None:
    store.mark_applied("alice", "job_a")
    assert store.unmark_applied("alice", "job_a") is True
    assert store.is_applied("alice", "job_a") is False


def test_unmark_applied_returns_false_when_absent(
    store: FileAppliedStore,
) -> None:
    assert store.unmark_applied("alice", "never_applied") is False


def test_persistence_across_instances(
    store: FileAppliedStore, tmp_path: Path
) -> None:
    store.mark_applied("alice", "job_a")
    store.mark_applied("alice", "job_b")
    fresh = FileAppliedStore(root=tmp_path / "applied")
    assert fresh.list_applied("alice") == {"job_a", "job_b"}


def test_users_isolated(store: FileAppliedStore) -> None:
    store.mark_applied("alice", "job_a")
    store.mark_applied("bob", "job_b")
    assert store.list_applied("alice") == {"job_a"}
    assert store.list_applied("bob") == {"job_b"}


def test_handles_url_unsafe_job_ids(store: FileAppliedStore) -> None:
    weird_id = "abc/123==/xyz"
    store.mark_applied("alice", weird_id)
    assert store.is_applied("alice", weird_id) is True
