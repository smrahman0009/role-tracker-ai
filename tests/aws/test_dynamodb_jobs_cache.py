"""Tests for DynamoDBJobsCache — same Protocol as FileJobsCache.

The point of this store is durability across container restarts, so
the round-trip + clear behaviour is what matters here.
"""

import pytest

from role_tracker.aws.dynamodb_jobs_cache import DynamoDBJobsCache
from role_tracker.jobs.models import JobPosting
from role_tracker.matching.scorer import ScoredJob
from tests.aws.conftest import make_users_table

TABLE_NAME = "role-tracker-jobs"


@pytest.fixture
def cache(dynamodb_resource: object) -> DynamoDBJobsCache:
    # The jobs table is partition-key-only (one snapshot per user),
    # same shape as the users table — reuse that helper.
    make_users_table(dynamodb_resource, TABLE_NAME)
    return DynamoDBJobsCache(TABLE_NAME, dynamodb_resource=dynamodb_resource)


def _scored(job_id: str = "j1", score: float = 0.81) -> ScoredJob:
    return ScoredJob(
        job=JobPosting(
            id=job_id,
            title="ML Engineer",
            company="Atlas AI",
            location="Toronto, ON",
            description="Build ranked-job pipelines.",
            url="https://example.com/atlas/ml",
            posted_at="2026-05-10",
            salary_min=160000,
            salary_max=200000,
            publisher="Atlas Careers",
        ),
        score=score,
    )


def test_get_returns_none_for_new_table(cache: DynamoDBJobsCache) -> None:
    assert cache.get_snapshot("alice") is None


def test_save_then_get_round_trips(cache: DynamoDBJobsCache) -> None:
    saved = cache.save_snapshot(
        "alice",
        [_scored("j1", 0.9), _scored("j2", 0.42)],
        candidates_seen=247,
        queries_run=3,
        top_n_cap=50,
    )
    fetched = cache.get_snapshot("alice")
    assert fetched is not None
    assert [s.job.id for s in fetched.jobs] == ["j1", "j2"]
    # Float scores must survive the JSON round-trip exactly.
    assert [s.score for s in fetched.jobs] == [0.9, 0.42]
    assert fetched.candidates_seen == 247
    assert fetched.queries_run == 3
    assert fetched.top_n_cap == 50
    assert fetched.last_refreshed_at == saved.last_refreshed_at


def test_save_overwrites_previous_snapshot(
    cache: DynamoDBJobsCache,
) -> None:
    cache.save_snapshot("alice", [_scored("old", 0.5)])
    cache.save_snapshot("alice", [_scored("new", 0.7)])
    fetched = cache.get_snapshot("alice")
    assert fetched is not None
    assert [s.job.id for s in fetched.jobs] == ["new"]


def test_snapshots_are_per_user(cache: DynamoDBJobsCache) -> None:
    cache.save_snapshot("alice", [_scored("a1")])
    cache.save_snapshot("bob", [_scored("b1")])
    alice = cache.get_snapshot("alice")
    bob = cache.get_snapshot("bob")
    assert alice is not None and bob is not None
    assert [s.job.id for s in alice.jobs] == ["a1"]
    assert [s.job.id for s in bob.jobs] == ["b1"]


def test_clear_returns_true_when_snapshot_existed(
    cache: DynamoDBJobsCache,
) -> None:
    cache.save_snapshot("alice", [_scored()])
    assert cache.clear_snapshot("alice") is True
    assert cache.get_snapshot("alice") is None


def test_clear_returns_false_when_nothing_to_clear(
    cache: DynamoDBJobsCache,
) -> None:
    assert cache.clear_snapshot("ghost") is False
