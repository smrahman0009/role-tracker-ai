"""Tests for the FileAppliedStore."""

from pathlib import Path

import pytest

from role_tracker.applied.store import FileAppliedStore


@pytest.fixture
def store(tmp_path: Path) -> FileAppliedStore:
    return FileAppliedStore(root=tmp_path / "applied")


def test_initially_empty(store: FileAppliedStore) -> None:
    assert store.list_applied("alice") == {}
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
    assert set(fresh.list_applied("alice").keys()) == {"job_a", "job_b"}


def test_users_isolated(store: FileAppliedStore) -> None:
    store.mark_applied("alice", "job_a")
    store.mark_applied("bob", "job_b")
    assert set(store.list_applied("alice").keys()) == {"job_a"}
    assert set(store.list_applied("bob").keys()) == {"job_b"}


def test_handles_url_unsafe_job_ids(store: FileAppliedStore) -> None:
    weird_id = "abc/123==/xyz"
    store.mark_applied("alice", weird_id)
    assert store.is_applied("alice", weird_id) is True


# ----- new rich-record tests -----


def test_mark_applied_records_timestamp_and_resume_metadata(
    store: FileAppliedStore,
) -> None:
    store.mark_applied(
        "alice",
        "job_a",
        resume_filename="shaikh_v3.pdf",
        resume_sha256="abc123",
        letter_version_used=3,
    )
    record = store.get_application("alice", "job_a")
    assert record is not None
    assert record.applied_at is not None  # set to now()
    assert record.resume_filename == "shaikh_v3.pdf"
    assert record.resume_sha256 == "abc123"
    assert record.letter_version_used == 3


def test_legacy_set_format_is_read_with_empty_records(
    store: FileAppliedStore, tmp_path: Path
) -> None:
    """Files written before the rich-record refactor have shape
    {"applied": [...]} — we read them as records with all fields blank."""
    import json

    legacy_path = tmp_path / "applied" / "alice.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(json.dumps({"applied": ["job_a", "job_b"]}))

    applications = store.list_applied("alice")
    assert set(applications.keys()) == {"job_a", "job_b"}
    # Empty records — we don't fabricate timestamps for legacy data.
    assert applications["job_a"].applied_at is None
    assert applications["job_a"].resume_filename == ""
