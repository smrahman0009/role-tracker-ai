"""Unit tests for cosine similarity + job ranking."""

import math

import pytest

from role_tracker.jobs.models import JobPosting
from role_tracker.matching.scorer import (
    cosine_similarity,
    job_to_embedding_text,
    rank_jobs,
)


def _job(id_: str, title: str, description: str = "") -> JobPosting:
    return JobPosting(
        id=id_,
        title=title,
        company="Acme",
        location="Toronto",
        description=description,
        url="https://example.com",
        posted_at="2026-04-14T08:00:00Z",
    )


def test_cosine_identical_vectors_is_one() -> None:
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_opposite_vectors_is_negative_one() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_zero_vector_returns_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])


def test_rank_jobs_returns_top_n_by_similarity() -> None:
    resume = [1.0, 0.0, 0.0]
    jobs = [_job("1", "A"), _job("2", "B"), _job("3", "C")]
    vectors = [
        [0.0, 1.0, 0.0],  # orthogonal, score 0
        [1.0, 0.0, 0.0],  # identical, score 1
        [1.0, 1.0, 0.0],  # score 1/sqrt(2)
    ]
    top = rank_jobs(resume, jobs, vectors, top_n=2)
    assert [s.job.id for s in top] == ["2", "3"]
    assert top[0].score == pytest.approx(1.0)
    assert top[1].score == pytest.approx(1.0 / math.sqrt(2))


def test_rank_jobs_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        rank_jobs([1.0], [_job("1", "A")], [[1.0], [2.0]], top_n=1)


def test_job_to_embedding_text_includes_title_and_description() -> None:
    job = _job("1", "Senior Data Scientist", description="Build ML models.")
    text = job_to_embedding_text(job)
    assert "Senior Data Scientist" in text
    assert "Build ML models." in text
