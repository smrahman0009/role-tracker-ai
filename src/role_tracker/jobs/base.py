"""Common contract every job source must implement.

Add a new source (e.g. SerpAPI) by creating a class with `.name` and
`.fetch_jobs(what, where, limit)` — it will plug into run_match automatically.
"""

from typing import Protocol

from role_tracker.jobs.models import JobPosting


class JobSource(Protocol):
    """Minimal interface: a name, and a way to fetch jobs."""

    name: str

    def fetch_jobs(
        self, *, what: str, where: str, limit: int
    ) -> list[JobPosting]: ...
