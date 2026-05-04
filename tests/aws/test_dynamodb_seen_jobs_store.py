"""Tests for DynamoDBSeenJobsStore — same Protocol as FileSeenJobsStore."""

import pytest

from role_tracker.aws.dynamodb_seen_jobs_store import DynamoDBSeenJobsStore
from role_tracker.jobs.models import JobPosting
from role_tracker.matching.scorer import ScoredJob
from tests.aws.conftest import make_table

TABLE_NAME = "role-tracker-seen-jobs"
SK = "job_id"


@pytest.fixture
def store(dynamodb_resource: object) -> DynamoDBSeenJobsStore:
    make_table(dynamodb_resource, TABLE_NAME, SK)
    return DynamoDBSeenJobsStore(
        TABLE_NAME, dynamodb_resource=dynamodb_resource
    )


def _job(job_id: str, **overrides: object) -> JobPosting:
    base = dict(
        id=job_id,
        title="Senior Data Scientist",
        company="Shopify",
        location="Toronto",
        description="Build ML models.",
        url="https://example.com/" + job_id,
        posted_at="2026-04-28T00:00:00Z",
        salary_min=120000.0,
        salary_max=160000.5,
    )
    base.update(overrides)
    return JobPosting(**base)


def test_get_missing_returns_none(store: DynamoDBSeenJobsStore) -> None:
    assert store.get("alice", "ghost") is None


def test_upsert_many_and_get(store: DynamoDBSeenJobsStore) -> None:
    store.upsert_many("alice", [ScoredJob(job=_job("j1"), score=0.92)])
    fetched = store.get("alice", "j1")
    assert fetched is not None
    assert fetched.job.id == "j1"
    assert fetched.score == pytest.approx(0.92)


def test_upsert_overwrites_existing(store: DynamoDBSeenJobsStore) -> None:
    store.upsert_many("alice", [ScoredJob(job=_job("j1"), score=0.5)])
    store.upsert_many("alice", [ScoredJob(job=_job("j1"), score=0.9)])
    fetched = store.get("alice", "j1")
    assert fetched is not None
    assert fetched.score == pytest.approx(0.9)


def test_upsert_empty_is_noop(store: DynamoDBSeenJobsStore) -> None:
    # Should not raise.
    store.upsert_many("alice", [])
    assert store.list_all("alice") == []


def test_list_all_returns_every_job(store: DynamoDBSeenJobsStore) -> None:
    store.upsert_many(
        "alice",
        [
            ScoredJob(job=_job("j1"), score=0.9),
            ScoredJob(job=_job("j2"), score=0.8),
            ScoredJob(job=_job("j3"), score=0.7),
        ],
    )
    listed = store.list_all("alice")
    assert {e.job.id for e in listed} == {"j1", "j2", "j3"}


def test_per_user_isolation(store: DynamoDBSeenJobsStore) -> None:
    store.upsert_many("alice", [ScoredJob(job=_job("j1"), score=0.9)])
    store.upsert_many("bob", [ScoredJob(job=_job("j2"), score=0.8)])
    assert store.get("alice", "j2") is None
    assert store.get("bob", "j1") is None


def test_remove_existing_returns_true(store: DynamoDBSeenJobsStore) -> None:
    store.upsert_many("alice", [ScoredJob(job=_job("j1"), score=0.9)])
    assert store.remove("alice", "j1") is True
    assert store.get("alice", "j1") is None


def test_remove_missing_returns_false(store: DynamoDBSeenJobsStore) -> None:
    assert store.remove("alice", "ghost") is False


def test_salary_round_trip_preserves_floats(
    store: DynamoDBSeenJobsStore,
) -> None:
    """JobPosting.salary_min/max are floats — must survive DynamoDB."""
    store.upsert_many(
        "alice",
        [
            ScoredJob(
                job=_job("j1", salary_min=120000.5, salary_max=160000.75),
                score=0.5,
            )
        ],
    )
    fetched = store.get("alice", "j1")
    assert fetched is not None
    assert fetched.job.salary_min == pytest.approx(120000.5)
    assert fetched.job.salary_max == pytest.approx(160000.75)


def test_batch_writer_handles_more_than_25_items(
    store: DynamoDBSeenJobsStore,
) -> None:
    """boto3's batch_writer handles the 25-item BatchWriteItem ceiling
    automatically — verify a 60-item upsert lands cleanly."""
    jobs = [
        ScoredJob(job=_job(f"j{i}"), score=0.5 + i / 100)
        for i in range(60)
    ]
    store.upsert_many("alice", jobs)
    assert len(store.list_all("alice")) == 60
