"""Keyword-based exclusion filters applied after fetching from any source."""

import re
from dataclasses import dataclass

from role_tracker.jobs.models import JobPosting

# Words to ignore when extracting "meaningful" tokens from a query.
_QUERY_STOPWORDS = {
    "a", "an", "and", "the", "or", "of", "in", "for",
    "with", "to", "at", "on", "by",
}


@dataclass
class ExcludedJob:
    job: JobPosting
    reason: str  # human-readable: which filter hit, and on what keyword


def _contains_any(haystack: str, needles: list[str]) -> str | None:
    """Return the first needle found in haystack (case-insensitive), else None."""
    hay = haystack.lower()
    for needle in needles:
        if needle.strip().lower() in hay:
            return needle
    return None


def _query_keywords(queries: list[str]) -> list[str]:
    """Extract meaningful keywords from a list of query phrases."""
    tokens: set[str] = set()
    for query in queries:
        for raw in re.split(r"[\s/,&\-]+", query.lower()):
            token = raw.strip()
            if len(token) >= 3 and token not in _QUERY_STOPWORDS:
                tokens.add(token)
    return sorted(tokens)


def apply_title_relevance(
    jobs: list[JobPosting],
    queries: list[str],
) -> tuple[list[JobPosting], list[ExcludedJob]]:
    """Drop jobs whose titles share no meaningful keyword with any query.

    Example: query="data scientist" → keywords={"data","scientist"}.
    A job titled "Backend Software Engineer" matches none → dropped.
    A job titled "Senior Data Engineer" matches "data" → kept.
    """
    keywords = _query_keywords(queries)
    if not keywords:
        return list(jobs), []
    kept: list[JobPosting] = []
    dropped: list[ExcludedJob] = []
    for job in jobs:
        title_lower = job.title.lower()
        if any(kw in title_lower for kw in keywords):
            kept.append(job)
        else:
            dropped.append(
                ExcludedJob(
                    job=job,
                    reason=(
                        f"title doesn't match any query keyword "
                        f"({', '.join(keywords)})"
                    ),
                )
            )
    return kept, dropped


def apply_exclusions(
    jobs: list[JobPosting],
    exclude_companies: list[str],
    exclude_title_keywords: list[str],
    exclude_publishers: list[str] | None = None,
) -> tuple[list[JobPosting], list[ExcludedJob]]:
    """Split jobs into (kept, excluded). Excluded jobs carry the drop reason."""
    exclude_publishers = exclude_publishers or []
    kept: list[JobPosting] = []
    dropped: list[ExcludedJob] = []
    for job in jobs:
        hit = _contains_any(job.company, exclude_companies)
        if hit:
            dropped.append(ExcludedJob(job=job, reason=f"company contains '{hit}'"))
            continue
        hit = _contains_any(job.title, exclude_title_keywords)
        if hit:
            dropped.append(ExcludedJob(job=job, reason=f"title contains '{hit}'"))
            continue
        hit = _contains_any(job.publisher, exclude_publishers)
        if hit:
            dropped.append(
                ExcludedJob(job=job, reason=f"publisher contains '{hit}'")
            )
            continue
        kept.append(job)
    return kept, dropped
