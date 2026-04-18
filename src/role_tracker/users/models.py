"""Per-user profile — one record per person the pipeline runs for."""

from pathlib import Path

from pydantic import BaseModel

from role_tracker.config import JobQuery


class UserProfile(BaseModel):
    """All per-user state: identity, resume, queries, and filters.

    Global pipeline settings (API keys, embedding model, country, page size)
    live in Settings / config.yaml and are shared across users.
    """

    id: str
    name: str
    email: str = ""
    resume_path: Path
    top_n_jobs: int = 5

    queries: list[JobQuery]
    exclude_companies: list[str] = []
    exclude_title_keywords: list[str] = []
    # Downstream publishers (Google-for-Jobs hosts) to block — filters low-quality
    # scraper sites like BeBee, Sercanto, Jobrapido. Passed to JSearch as a
    # server-side filter AND re-checked locally in case anything slips through.
    exclude_publishers: list[str] = []

    @property
    def resume_embedding_cache_path(self) -> Path:
        """Where to cache this user's resume embedding on disk."""
        return self.resume_path.with_suffix(".embedding.json")
