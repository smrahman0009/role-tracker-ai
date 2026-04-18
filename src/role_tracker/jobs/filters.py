"""Keyword-based exclusion filters applied after fetching from any source."""

from dataclasses import dataclass

from role_tracker.jobs.models import JobPosting


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
