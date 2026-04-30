"""End-to-end matching pipeline as a single function.

Wraps the existing engine — JSearch fetch, exclusion filters, title
relevance, embedding, ranking — into one callable. Both the API
(refresh endpoint) and the CLI (run_match.py) can call this.

The function is pure-ish in the sense that all dependencies (queries,
resume text, embedder, JSearch client, exclusion lists, top_n) are
arguments. This makes the function trivially testable: tests inject
a fake embedder and a fake JSearch client.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from role_tracker.config import JobQuery
from role_tracker.jobs.filters import apply_exclusions, apply_title_relevance
from role_tracker.jobs.jsearch import JSearchClient
from role_tracker.jobs.models import JobPosting
from role_tracker.matching.embeddings import Embedder, load_or_embed_resume
from role_tracker.matching.scorer import (
    ScoredJob,
    job_to_embedding_text,
    rank_jobs,
)
from role_tracker.queries.models import SavedQuery


@dataclass
class MatchingResult:
    """Output of run_matching_pipeline.

    Carries the ranked list plus enough stats for the UI to be honest
    about what happened ("kept 50 of 247 candidates from 4 searches").
    """

    jobs: list[ScoredJob] = field(default_factory=list)
    candidates_seen: int = 0   # post-filter, pre-rank — what got embedded
    queries_run: int = 0       # number of enabled saved searches fanned out


def run_matching_pipeline(
    *,
    queries: list[SavedQuery],
    resume_text: str,
    resume_embedding_cache_path: Path,
    embedder: Embedder,
    jsearch_client: JSearchClient,
    exclude_companies: list[str],
    exclude_title_keywords: list[str],
    exclude_publishers: list[str],
    limit_per_query: int,
    top_n: int,
) -> MatchingResult:
    """Fetch → filter → embed → rank.

    Returns the top_n ranked ScoredJobs plus pipeline stats. May return
    fewer than top_n if not enough jobs survived filtering.
    """
    enabled_queries = [q for q in queries if q.enabled]
    if not enabled_queries:
        return MatchingResult()

    # 1. Embed resume (hash-cached on disk to avoid re-embedding when text
    #    is unchanged).
    resume_vector = load_or_embed_resume(
        embedder, resume_text, resume_embedding_cache_path
    )

    # 2. Fetch from each query, dedupe by (title, company).
    seen: dict[tuple[str, str], JobPosting] = {}
    for q in enabled_queries:
        job_query = JobQuery(what=q.what, where=q.where)
        try:
            fetched = jsearch_client.fetch_jobs(
                what=job_query.what, where=job_query.where, limit=limit_per_query
            )
        except Exception:  # noqa: BLE001
            # One query failing shouldn't kill the whole refresh.
            continue
        for job in fetched:
            key = (job.title.strip().lower(), job.company.strip().lower())
            seen.setdefault(key, job)

    jobs = list(seen.values())
    if not jobs:
        return MatchingResult(queries_run=len(enabled_queries))

    # 3. Apply user exclusions (company / title-keyword / publisher).
    jobs, _ = apply_exclusions(
        jobs,
        exclude_companies=exclude_companies,
        exclude_title_keywords=exclude_title_keywords,
        exclude_publishers=exclude_publishers,
    )

    # 4. Title-relevance filter — drops backend roles for "data scientist", etc.
    query_strings = [q.what for q in enabled_queries]
    jobs, _ = apply_title_relevance(jobs, query_strings)

    if not jobs:
        return MatchingResult(queries_run=len(enabled_queries))

    candidates_seen = len(jobs)

    # 5. Embed jobs + rank.
    job_vectors = embedder.embed([job_to_embedding_text(j) for j in jobs])
    ranked = rank_jobs(resume_vector, jobs, job_vectors, top_n=top_n)
    return MatchingResult(
        jobs=ranked,
        candidates_seen=candidates_seen,
        queries_run=len(enabled_queries),
    )


# Type alias used by the API layer for dependency injection.
PipelineRunner = Callable[[str, list[SavedQuery], str], MatchingResult]
