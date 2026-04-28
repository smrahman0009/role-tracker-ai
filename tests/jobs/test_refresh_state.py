"""Tests for FileRefreshTaskStore + stale-task sweep."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from role_tracker.jobs.refresh_state import (
    STALE_AFTER_SECONDS,
    FileRefreshTaskStore,
    RefreshRecord,
)


@pytest.fixture
def store(tmp_path: Path) -> FileRefreshTaskStore:
    return FileRefreshTaskStore(root=tmp_path / "jobs")


def test_create_returns_pending_record(store: FileRefreshTaskStore) -> None:
    record = store.create("alice", "ref_001")
    assert record.refresh_id == "ref_001"
    assert record.status == "pending"
    assert record.completed_at is None


def test_get_returns_created_record(store: FileRefreshTaskStore) -> None:
    store.create("alice", "ref_001")
    record = store.get("alice", "ref_001")
    assert record is not None
    assert record.status == "pending"


def test_get_returns_none_when_missing(store: FileRefreshTaskStore) -> None:
    assert store.get("alice", "nonexistent") is None


def test_lifecycle_pending_running_done(store: FileRefreshTaskStore) -> None:
    store.create("alice", "ref_001")
    store.mark_running("alice", "ref_001")
    assert store.get("alice", "ref_001").status == "running"

    store.mark_done("alice", "ref_001", jobs_added=12)
    record = store.get("alice", "ref_001")
    assert record.status == "done"
    assert record.jobs_added == 12
    assert record.completed_at is not None


def test_lifecycle_pending_running_failed(store: FileRefreshTaskStore) -> None:
    store.create("alice", "ref_001")
    store.mark_running("alice", "ref_001")
    store.mark_failed("alice", "ref_001", error="JSearch quota exceeded")

    record = store.get("alice", "ref_001")
    assert record.status == "failed"
    assert record.error == "JSearch quota exceeded"


def test_stale_running_record_auto_marked_failed(
    tmp_path: Path,
) -> None:
    """A record stuck on 'running' for >5 min should be swept on read."""
    store = FileRefreshTaskStore(root=tmp_path / "jobs")
    store.create("alice", "ref_old")

    # Manually backdate the started_at to 6 minutes ago and force status=running.
    path = tmp_path / "jobs" / "alice" / "refreshes.json"
    import json

    data = json.loads(path.read_text())
    data["refreshes"][0]["status"] = "running"
    data["refreshes"][0]["started_at"] = (
        datetime.now(UTC) - timedelta(seconds=STALE_AFTER_SECONDS + 60)
    ).isoformat()
    path.write_text(json.dumps(data))

    # The first get() after the file is stale should auto-mark failed.
    record = store.get("alice", "ref_old")
    assert record is not None
    assert record.status == "failed"
    assert record.error is not None
    assert "timed out" in record.error.lower()
    # And the change persists on disk.
    persisted = json.loads(path.read_text())
    assert persisted["refreshes"][0]["status"] == "failed"


def test_running_record_within_window_not_swept(
    store: FileRefreshTaskStore,
) -> None:
    store.create("alice", "ref_fresh")
    store.mark_running("alice", "ref_fresh")
    record = store.get("alice", "ref_fresh")
    assert record.status == "running"  # not swept


def test_users_isolated(store: FileRefreshTaskStore) -> None:
    store.create("alice", "ref_a")
    store.create("bob", "ref_b")
    assert store.get("alice", "ref_a") is not None
    assert store.get("alice", "ref_b") is None
    assert store.get("bob", "ref_b") is not None


def test_record_serialization() -> None:
    """RefreshRecord should serialize / deserialize cleanly via Pydantic."""
    r = RefreshRecord(
        refresh_id="ref_001",
        status="running",
        started_at=datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC),
    )
    data = r.model_dump_json()
    restored = RefreshRecord.model_validate_json(data)
    assert restored.refresh_id == "ref_001"
    assert restored.status == "running"
