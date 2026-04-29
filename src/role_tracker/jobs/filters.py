"""Keyword-based exclusion filters applied after fetching from any source.

Two layers of filtering:
1. apply_exclusions / apply_title_relevance — applied at fetch time,
   based on the user's stable "Hidden" lists and active query keywords.
2. apply_list_filters — applied at request time on the cached snapshot,
   based on the inline filter chips on the Job List page.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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


# ====================================================================
# Inline list filters — applied at GET /jobs request time on the cached
# snapshot. Distinct from apply_exclusions (which runs at fetch time).
# ====================================================================


def apply_list_filters(
    jobs: list[JobPosting],
    *,
    type_terms: list[str],
    location_terms: list[str],
    salary_min: int | None,
    hide_no_salary: bool,
    employment_types: list[str],
    posted_within_days: int | None,
) -> list[JobPosting]:
    """Apply the inline filter-chip filters from GET /jobs.

    Each filter is independent (AND across filter types); within a
    multi-value filter (type/location/employment_types), values are
    OR-combined. Empty filter lists or None values mean "no filter on
    this dimension."

    All match logic is case-insensitive and uses substring containment
    for type/location (so "Senior Data Scientist" matches type="data
    scientist").
    """
    cutoff = (
        datetime.now(UTC) - timedelta(days=posted_within_days)
        if posted_within_days
        else None
    )
    type_terms_lower = [t.lower().strip() for t in type_terms if t.strip()]
    location_terms_lower = [
        loc.lower().strip() for loc in location_terms if loc.strip()
    ]
    employment_set = {e.upper().strip() for e in employment_types if e.strip()}

    out: list[JobPosting] = []
    for job in jobs:
        # Type (multi-value, OR within)
        if type_terms_lower:
            title_lower = job.title.lower()
            if not any(t in title_lower for t in type_terms_lower):
                continue

        # Location (multi-value, OR within)
        if location_terms_lower:
            location_lower = job.location.lower()
            if not any(loc in location_lower for loc in location_terms_lower):
                continue

        # Salary minimum
        if salary_min is not None:
            if job.salary_min is None:
                if hide_no_salary:
                    continue
                # else: lenient — keep jobs with no listed salary
            elif job.salary_min < salary_min:
                continue

        # Employment type (multi-value, OR within; empty types pass through)
        if employment_set:
            if job.employment_type and job.employment_type not in employment_set:
                continue

        # Posted within
        if cutoff is not None:
            try:
                posted = datetime.fromisoformat(
                    job.posted_at.replace("Z", "+00:00")
                )
                if posted.tzinfo is None:
                    posted = posted.replace(tzinfo=UTC)
                if posted < cutoff:
                    continue
            except (ValueError, AttributeError):
                # Unparseable timestamp — keep the job (lenient).
                pass

        out.append(job)
    return out
