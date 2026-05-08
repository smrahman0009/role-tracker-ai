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
    portfolio_url: str = ""
    resume_path: Path
    # How many ranked matches to keep per refresh. Default chosen for a
    # browseable list — past ~100 the long tail is mostly low-similarity
    # noise. Capped in the API at 200.
    top_n_jobs: int = 50

    # Per-field "show in cover-letter header" flags. All default True; the
    # contact_header() builder respects them. Empty fields are skipped
    # regardless of flag (you can't render a blank line). Name is always
    # shown.
    show_phone_in_header: bool = True
    show_email_in_header: bool = True
    show_city_in_header: bool = True
    show_linkedin_in_header: bool = True
    show_github_in_header: bool = True
    show_portfolio_in_header: bool = True

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
        """Formatted header block used at the top of every cover letter.

        Respects per-field show-in-header flags. Empty fields are skipped
        regardless. Name is always rendered.
        """
        contact_parts: list[str] = []
        if self.phone and self.show_phone_in_header:
            contact_parts.append(self.phone)
        if self.email and self.show_email_in_header:
            contact_parts.append(self.email)
        if self.city and self.show_city_in_header:
            contact_parts.append(self.city)

        # Render URLs as plain text (with the https:// scheme) rather
        # than markdown [Label](url) syntax. Many ATS scrapers strip
        # markdown links and lose the URL entirely; spelling the URL
        # out keeps it both human-readable and ATS-parseable. PDF /
        # markdown viewers will still auto-link the bare URL on click.
        links: list[str] = []
        if self.linkedin_url and self.show_linkedin_in_header:
            links.append(self.linkedin_url)
        if self.github_url and self.show_github_in_header:
            links.append(self.github_url)
        if self.portfolio_url and self.show_portfolio_in_header:
            links.append(self.portfolio_url)

        lines = [f"**{self.name}**"]
        if contact_parts:
            lines.append(" | ".join(contact_parts))
        if links:
            lines.append(" | ".join(links))
        return "\n".join(lines)
