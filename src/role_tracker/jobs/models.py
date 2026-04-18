"""Shared data model for a single job posting — source-agnostic."""

from pydantic import BaseModel


class JobPosting(BaseModel):
    """A single job posting, normalized across every source (Adzuna, JSearch, ...)."""

    id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    posted_at: str
    salary_min: float | None = None
    salary_max: float | None = None
    source: str = "unknown"  # which provider this came from (e.g. "adzuna")
    publisher: str = "unknown"  # the downstream site hosting the listing (e.g. "BeBee")
