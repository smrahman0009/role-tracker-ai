"""Cosine similarity + ranking of job postings against a resume vector."""

import math
from dataclasses import dataclass

from role_tracker.jobs.models import JobPosting


@dataclass
class ScoredJob:
    job: JobPosting
    score: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors. Returns 0 if either is zero."""
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def job_to_embedding_text(job: JobPosting) -> str:
    """Text blob representing a job for embedding."""
    return f"{job.title}\n\n{job.description}"


def rank_jobs(
    resume_vector: list[float],
    jobs: list[JobPosting],
    job_vectors: list[list[float]],
    top_n: int,
) -> list[ScoredJob]:
    """Return the top-N jobs by cosine similarity, highest first."""
    if len(jobs) != len(job_vectors):
        raise ValueError(
            f"jobs/vectors length mismatch: {len(jobs)} vs {len(job_vectors)}"
        )
    scored = [
        ScoredJob(job=job, score=cosine_similarity(resume_vector, vec))
        for job, vec in zip(jobs, job_vectors, strict=True)
    ]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:top_n]
