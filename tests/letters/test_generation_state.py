"""Tests for FileLetterGenerationStore + stale-task sweep."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from role_tracker.letters.generation_state import (
    STALE_AFTER_SECONDS,
    FileLetterGenerationStore,
)


@pytest.fixture
def store(tmp_path: Path) -> FileLetterGenerationStore:
    return FileLetterGenerationStore(root=tmp_path / "letters")


def test_create_returns_pending(store: FileLetterGenerationStore) -> None:
    record = store.create("alice", "gen_001", job_id="job_a")
    assert record.status == "pending"
    assert record.job_id == "job_a"
    assert record.saved_version is None


def test_lifecycle_pending_running_done(
    store: FileLetterGenerationStore,
) -> None:
    store.create("alice", "gen_001", job_id="job_a")
    store.mark_running("alice", "gen_001")
    assert store.get("alice", "gen_001").status == "running"

    store.mark_done("alice", "gen_001", saved_version=1)
    record = store.get("alice", "gen_001")
    assert record.status == "done"
    assert record.saved_version == 1
    assert record.completed_at is not None


def test_mark_failed(store: FileLetterGenerationStore) -> None:
    store.create("alice", "gen_001", job_id="job_a")
    store.mark_failed("alice", "gen_001", error="No resume")
    record = store.get("alice", "gen_001")
    assert record.status == "failed"
    assert record.error == "No resume"


def test_get_returns_none_for_missing(
    store: FileLetterGenerationStore,
) -> None:
    assert store.get("alice", "nonexistent") is None


def test_stale_running_record_swept(tmp_path: Path) -> None:
    store = FileLetterGenerationStore(root=tmp_path / "letters")
    store.create("alice", "gen_old", job_id="job_a")

    path = tmp_path / "letters" / "alice" / "_generations.json"
    data = json.loads(path.read_text())
    data["generations"][0]["status"] = "running"
    data["generations"][0]["started_at"] = (
        datetime.now(UTC) - timedelta(seconds=STALE_AFTER_SECONDS + 60)
    ).isoformat()
    path.write_text(json.dumps(data))

    record = store.get("alice", "gen_old")
    assert record.status == "failed"
    assert "timed out" in (record.error or "").lower()


def test_users_isolated(store: FileLetterGenerationStore) -> None:
    store.create("alice", "gen_a", job_id="job_x")
    store.create("bob", "gen_b", job_id="job_x")
    assert store.get("alice", "gen_a") is not None
    assert store.get("alice", "gen_b") is None
    assert store.get("bob", "gen_b") is not None
