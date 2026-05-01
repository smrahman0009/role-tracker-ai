"""Best-effort job-description extraction from a URL.

Used by the "Add a job manually" flow as a convenience: paste a URL,
backend tries to fetch and extract the job description; if extraction
fails or returns garbage, the user pastes the JD into a textarea
themselves. We never block the workflow on a successful fetch.

Honest caveats:
- Works well on Greenhouse / Lever / Ashby / Workable / static company
  career pages (~70% of legit job postings live there).
- Fails on Workday (heavy JS SPA — content not in the initial HTML),
  LinkedIn / Indeed / Glassdoor (Cloudflare bot detection, 403).
- Returns short / empty text from sites where Trafilatura can't find a
  main content block — caller should treat that as failure and ask the
  user to paste manually.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel
import trafilatura


# Anything shorter than this almost certainly isn't a real JD — caller
# should fall back to manual paste.
MIN_DESCRIPTION_CHARS = 200


class ExtractedJob(BaseModel):
    """What we managed to pull from a URL. Any field may be empty."""

    title: str = ""
    company: str = ""
    description: str = ""


def extract_job_from_url(
    url: str, *, http_client: httpx.Client | None = None
) -> ExtractedJob:
    """Fetch the URL and try to pull job-posting fields.

    Returns an ExtractedJob with whatever we found. Empty fields signal
    that we couldn't extract that piece — the frontend will show the
    textarea prefilled with whatever description we got, blank if none.
    Never raises on fetch / parse failure.
    """
    client = http_client or httpx.Client(
        follow_redirects=True,
        timeout=15.0,
        headers={
            # Some sites 403 on the default httpx UA. Generic Chrome UA
            # is enough for the static-HTML targets we care about.
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        try:
            response = client.get(url)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.InvalidURL):
            return ExtractedJob()
        html = response.text
    finally:
        if http_client is None:
            client.close()

    description = trafilatura.extract(html) or ""
    if len(description.strip()) < MIN_DESCRIPTION_CHARS:
        description = ""

    metadata = trafilatura.extract_metadata(html)
    title = (metadata.title if metadata and metadata.title else "") or ""
    # Site-name often holds the company on career-page subdomains
    # (e.g. "Acme Careers"). Strip the trailing " Careers" / " Jobs"
    # noise so the user gets a sensible default.
    raw_company = (metadata.sitename if metadata and metadata.sitename else "") or ""
    company = _clean_company(raw_company)

    return ExtractedJob(
        title=title.strip(),
        company=company.strip(),
        description=description.strip(),
    )


def _clean_company(raw: str) -> str:
    """Trim common trailing noise from extracted site names."""
    s = raw.strip()
    for suffix in (" Careers", " Jobs", " - Careers", " | Careers"):
        if s.lower().endswith(suffix.lower()):
            s = s[: -len(suffix)].strip()
    return s
