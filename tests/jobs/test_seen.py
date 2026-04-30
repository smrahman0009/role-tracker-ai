"""Tests for FileSeenJobsStore."""

from pathlib import Path

import pytest

from role_tracker.jobs.models import JobPosting
from role_tracker.jobs.seen import FileSeenJobsStore
from role_tracker.matching.scorer import ScoredJob


def _job(job_id: str = "abc", title: str = "Data Scientist") -> JobPosting:
    return JobPosting(
        id=job_id,
        title=title,
        company="Acme",
        location="Toronto",
        description="Build models.",
        url="https://example.com",
        posted_at="2026-04-28T00:00:00Z",
        source="jsearch",
        publisher="Acme Careers",
    )


@pytest.fixture
def store(tmp_path: Path) -> FileSeenJobsStore:
    return FileSeenJobsStore(root=tmp_path / "seen")


def test_get_returns_none_when_unseen(store: FileSeenJobsStore) -> None:
    assert store.get("alice", "missing") is None


def test_upsert_then_get_round_trip(store: FileSeenJobsStore) -> None:
    store.upsert_many(
        "alice",
        [ScoredJob(job=_job("a"), score=0.9)],
    )
    found = store.get("alice", "a")
    assert found is not None
    assert found.job.id == "a"
    assert found.score == 0.9


def test_upsert_replaces_existing_entry(store: FileSeenJobsStore) -> None:
    store.upsert_many("alice", [ScoredJob(job=_job("a"), score=0.5)])
    store.upsert_many("alice", [ScoredJob(job=_job("a"), score=0.9)])
    found = store.get("alice", "a")
    assert found is not None
    assert found.score == 0.9  # latest wins


def test_upsert_preserves_other_entries(store: FileSeenJobsStore) -> None:
    store.upsert_many(
        "alice",
        [ScoredJob(job=_job("a"), score=0.5), ScoredJob(job=_job("b"), score=0.7)],
    )
    # Second search adds c, updates b
    store.upsert_many(
        "alice",
        [ScoredJob(job=_job("b"), score=0.8), ScoredJob(job=_job("c"), score=0.6)],
    )
    assert store.get("alice", "a") is not None  # unchanged
    assert store.get("alice", "b").score == 0.8  # type: ignore[union-attr]
    assert store.get("alice", "c") is not None


def test_users_are_isolated(store: FileSeenJobsStore) -> None:
    store.upsert_many("alice", [ScoredJob(job=_job("a"), score=0.9)])
    assert store.get("bob", "a") is None


def test_empty_upsert_is_noop(store: FileSeenJobsStore, tmp_path: Path) -> None:
    store.upsert_many("alice", [])
    assert not (tmp_path / "seen" / "alice.json").exists()
