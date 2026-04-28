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
    phone: str = ""
    city: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    resume_path: Path
    top_n_jobs: int = 5

    queries: list[JobQuery]
    exclude_companies: list[str] = []
    exclude_title_keywords: list[str] = []
    # Downstream publisher names the user has chosen to filter out of their
    # results. Passed to JSearch as a server-side filter AND re-checked
    # locally. Personal preference list — no implied judgment about the
    # named publishers.
    exclude_publishers: list[str] = []

    @property
    def resume_embedding_cache_path(self) -> Path:
        """Where to cache this user's resume embedding on disk."""
        return self.resume_path.with_suffix(".embedding.json")

    def contact_header(self) -> str:
        """Formatted header block used at the top of every cover letter."""
        contact_parts: list[str] = []
        if self.phone:
            contact_parts.append(self.phone)
        if self.email:
            contact_parts.append(self.email)
        if self.city:
            contact_parts.append(self.city)
        links = [
            f"[LinkedIn]({self.linkedin_url})" if self.linkedin_url else "",
            f"[GitHub]({self.github_url})" if self.github_url else "",
        ]
        links = [link for link in links if link]

        lines = [f"**{self.name}**"]
        if contact_parts:
            lines.append(" | ".join(contact_parts))
        if links:
            lines.append(" | ".join(links))
        return "\n".join(lines)
