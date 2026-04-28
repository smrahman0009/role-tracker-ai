"""Tests for the FileJobsCache."""

from pathlib import Path

import pytest

from role_tracker.jobs.cache import FileJobsCache, StoredScoredJob
from role_tracker.jobs.models import JobPosting
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
def cache(tmp_path: Path) -> FileJobsCache:
    return FileJobsCache(root=tmp_path / "jobs")


def test_get_snapshot_returns_none_when_empty(cache: FileJobsCache) -> None:
    assert cache.get_snapshot("alice") is None


def test_save_then_get_round_trip(cache: FileJobsCache) -> None:
    scored = [
        ScoredJob(job=_job("a", "Title A"), score=0.9),
        ScoredJob(job=_job("b", "Title B"), score=0.8),
    ]
    saved = cache.save_snapshot("alice", scored)
    assert saved.last_refreshed_at is not None
    assert len(saved.jobs) == 2

    loaded = cache.get_snapshot("alice")
    assert loaded is not None
    assert len(loaded.jobs) == 2
    assert loaded.jobs[0].job.title == "Title A"
    assert loaded.jobs[0].score == 0.9


def test_save_replaces_previous_snapshot(cache: FileJobsCache) -> None:
    cache.save_snapshot("alice", [ScoredJob(job=_job("a"), score=0.5)])
    cache.save_snapshot(
        "alice",
        [
            ScoredJob(job=_job("b"), score=0.7),
            ScoredJob(job=_job("c"), score=0.6),
        ],
    )
    loaded = cache.get_snapshot("alice")
    assert loaded is not None
    assert {s.job.id for s in loaded.jobs} == {"b", "c"}


def test_users_isolated(cache: FileJobsCache) -> None:
    cache.save_snapshot("alice", [ScoredJob(job=_job("a"), score=0.9)])
    cache.save_snapshot("bob", [ScoredJob(job=_job("b"), score=0.8)])

    alice = cache.get_snapshot("alice")
    bob = cache.get_snapshot("bob")
    assert alice is not None and bob is not None
    assert alice.jobs[0].job.id == "a"
    assert bob.jobs[0].job.id == "b"


def test_stored_scored_job_round_trip() -> None:
    original = ScoredJob(job=_job("x"), score=0.42)
    stored = StoredScoredJob.from_scored(original)
    restored = stored.to_scored()
    assert restored.score == 0.42
    assert restored.job.id == "x"
