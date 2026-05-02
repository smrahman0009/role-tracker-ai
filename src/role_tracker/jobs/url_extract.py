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

import json

import httpx
from anthropic import Anthropic
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


# ----- LLM-refined extraction (handles recruiter / aggregator pages) -----


_LLM_MODEL = "claude-haiku-4-5-20251001"

_LLM_SYSTEM = """\
You read a job posting (often noisy — pulled from a recruiter
agency, aggregator, or career page that includes surrounding chrome)
and extract four clean fields. The candidate cares about the role,
not the publisher.

OUTPUT
Return ONLY a JSON object with these four keys:
  {"company": "...", "title": "...", "location": "...", "description": "..."}

RULES
- "company" = the actual employer mentioned in the JD body. If the JD
  says "Our client, ABC Corp, is hiring..." then company = "ABC Corp",
  NOT the recruiter agency. If the JD says "We at ABC Corp are looking
  for..." then company = "ABC Corp".
  If the JD never names the actual employer (recruiter keeping it
  confidential), set company to "" — DO NOT guess.

- "title" = the clean role title from the JD. Strip aggregator noise
  like "Job ID 12345 - ", "(Hybrid - Remote OK) - ", "Apply Now: ",
  date prefixes, leading/trailing whitespace.
  If the JD doesn't have a clear title, set title to "".

- "location" = where the role is based, as written. Examples: "Halifax,
  NS", "Toronto, Canada", "Remote", "Remote, US", "London, UK (Hybrid)",
  "San Francisco or Remote". Just the location string — no preamble.
  If the JD doesn't specify, set location to "".

- "description" = the cleaned job description. KEEP only role-specific
  content: summary of the role, responsibilities, requirements,
  qualifications, tech stack, what success looks like, salary if
  mentioned. STRIP boilerplate that surrounds many postings:
  · "About [Company]" / "Who we are" sections that read like marketing
  · "Equal Opportunity Employer" / DEI statements
  · "How to apply" / submission instructions
  · "Other openings" / "More jobs at this company"
  · cookie banners, nav links, footer text
  · benefits boilerplate that's not specific to the role
  Preserve paragraph structure. Keep specific benefits paragraphs
  (e.g., "$X salary range, equity, healthcare") because they're
  candidate-relevant.
  If the input has no recognizable JD content (page was empty or
  navigation-only), set description to "".

- Output the JSON object only — no preamble, no markdown code fences.
"""


def refine_with_llm(
    *, description: str, client: Anthropic, model: str = _LLM_MODEL
) -> dict[str, str]:
    """Pull company / title / location / cleaned description from the JD
    body via Haiku.

    Returns a dict with all four keys; any value may be empty when the
    JD doesn't supply that field. Returns all-empty silently on any LLM
    failure — caller decides whether to fall back to Trafilatura's raw
    output.
    """
    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=_LLM_SYSTEM,
            messages=[{"role": "user", "content": description.strip()[:12000]}],
        )
        text = "".join(
            b.text
            for b in response.content
            if getattr(b, "type", None) == "text"
        ).strip()
        # Strip optional markdown fence the model occasionally produces.
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        parsed = json.loads(text)
        return {
            "company": str(parsed.get("company", "")).strip(),
            "title": str(parsed.get("title", "")).strip(),
            "location": str(parsed.get("location", "")).strip(),
            "description": str(parsed.get("description", "")).strip(),
        }
    except Exception:  # noqa: BLE001
        return {"company": "", "title": "", "location": "", "description": ""}
