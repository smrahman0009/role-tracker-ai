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

import html as html_lib
import json
import re

import httpx
import trafilatura
from anthropic import Anthropic
from pydantic import BaseModel

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

    Strategy (each step falls through to the next on no match):
      1. ATS-specific JSON endpoints (Workable, Greenhouse, Lever).
         These ATSes render their public job pages with a React SPA — the
         server-side HTML is an empty shell and Trafilatura can't extract
         anything. But each ATS exposes a no-auth JSON API that the SPA
         itself uses, returning the full structured posting.
      2. Schema.org JSON-LD JobPosting embedded in the HTML. Common on
         large-company career sites (KPMG, banks, consultancies). More
         reliable than Trafilatura because the fields are explicit.
      3. Trafilatura on the rendered HTML for everything else (static
         company career pages, blog-style postings).

    Returns an ExtractedJob with whatever we found. Empty fields signal
    that we couldn't extract that piece — the frontend then asks the
    user to paste manually. Never raises on fetch / parse failure.
    """
    client = http_client or httpx.Client(
        follow_redirects=True,
        timeout=15.0,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        # 1. ATS-specific extractors (no Trafilatura needed).
        for matcher in _ATS_EXTRACTORS:
            try:
                ats_result = matcher(url, client)
            except Exception:  # noqa: BLE001
                ats_result = None
            if ats_result is not None:
                return ats_result

        # 2. Fetch the page once for the remaining strategies.
        try:
            response = client.get(url)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.InvalidURL):
            return ExtractedJob()
        html = response.text

        # 3. JSON-LD JobPosting (schema.org) — works on KPMG, banks,
        # consultancies, anything that bothered to ship structured data.
        jsonld = _extract_from_jsonld(html)
        if jsonld is not None and jsonld.description:
            return jsonld
    finally:
        if http_client is None:
            client.close()

    # 4. Trafilatura fallback for anything that got us this far.
    description = trafilatura.extract(html) or ""
    if len(description.strip()) < MIN_DESCRIPTION_CHARS:
        description = ""

    metadata = trafilatura.extract_metadata(html)
    title = (metadata.title if metadata and metadata.title else "") or ""
    raw_company = (metadata.sitename if metadata and metadata.sitename else "") or ""
    company = _clean_company(raw_company)

    return ExtractedJob(
        title=title.strip(),
        company=company.strip(),
        description=description.strip(),
    )


# ----- ATS-specific JSON extractors -----
#
# Each function takes (url, http_client) and returns ExtractedJob if it
# matched its ATS pattern AND fetched the JSON successfully, else None.
# Order in _ATS_EXTRACTORS doesn't matter since the URL patterns are
# disjoint.


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    """Convert ATS HTML field (description / requirements / benefits)
    to plain text. ATS APIs return HTML strings; we want clean prose
    for the JD textarea + downstream LLM cleaning.

    Also decodes named entities (&rsquo; &nbsp; &amp; etc.) and
    converts <br> / <p> / <li> into line breaks so paragraph structure
    survives the strip.
    """
    if not s:
        return ""
    # Convert structural tags to whitespace BEFORE blanket-stripping the rest,
    # so paragraph breaks and list bullets don't collapse into one big line.
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", s)
    text = re.sub(r"(?i)</\s*(p|div|h[1-6]|li)\s*>", "\n\n", text)
    text = re.sub(r"(?i)<\s*li[^>]*>", "• ", text)
    text = _HTML_TAG_RE.sub("", text)
    text = html_lib.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


_WORKABLE_RE = re.compile(
    r"^https?://apply\.workable\.com/([^/]+)/j/([^/?#]+)", re.IGNORECASE
)


def _extract_workable(url: str, client: httpx.Client) -> ExtractedJob | None:
    m = _WORKABLE_RE.match(url)
    if not m:
        return None
    tenant, shortcode = m.group(1), m.group(2)
    api = (
        f"https://apply.workable.com/api/v1/accounts/"
        f"{tenant}/jobs/{shortcode}"
    )
    r = client.get(api, headers={"Accept": "application/json"})
    if r.status_code != 200:
        return None
    data = r.json()
    title = (data.get("title") or "").strip()
    # Compose the JD from description + requirements + benefits — these
    # are separate HTML fields in Workable's schema. We strip tags here
    # so the JD is plain text the LLM can clean further.
    parts = [
        _strip_html(data.get("description") or ""),
        _strip_html(data.get("requirements") or ""),
        _strip_html(data.get("benefits") or ""),
    ]
    description = "\n\n".join(p for p in parts if p)
    return ExtractedJob(
        title=title,
        company=tenant.replace("-", " ").title(),
        description=description,
    )


_GREENHOUSE_RE = re.compile(
    r"^https?://boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", re.IGNORECASE
)


def _extract_greenhouse(
    url: str, client: httpx.Client
) -> ExtractedJob | None:
    m = _GREENHOUSE_RE.match(url)
    if not m:
        return None
    board, job_id = m.group(1), m.group(2)
    api = (
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    )
    r = client.get(api, headers={"Accept": "application/json"})
    if r.status_code != 200:
        return None
    data = r.json()
    return ExtractedJob(
        title=(data.get("title") or "").strip(),
        company=board.replace("-", " ").title(),
        description=_strip_html(data.get("content") or ""),
    )


_LEVER_RE = re.compile(
    r"^https?://jobs\.lever\.co/([^/]+)/([^/?#]+)", re.IGNORECASE
)


def _extract_lever(url: str, client: httpx.Client) -> ExtractedJob | None:
    m = _LEVER_RE.match(url)
    if not m:
        return None
    company, posting_id = m.group(1), m.group(2)
    api = f"https://api.lever.co/v0/postings/{company}/{posting_id}"
    r = client.get(
        api, params={"mode": "json"}, headers={"Accept": "application/json"}
    )
    if r.status_code != 200:
        return None
    data = r.json()
    # Lever splits the JD across descriptionPlain + lists[].content
    parts: list[str] = []
    if data.get("descriptionPlain"):
        parts.append(data["descriptionPlain"].strip())
    elif data.get("description"):
        parts.append(_strip_html(data["description"]))
    for lst in data.get("lists") or []:
        text = (lst.get("text") or "").strip()
        content = _strip_html(lst.get("content") or "")
        if text or content:
            parts.append(f"{text}\n{content}".strip())
    if data.get("additionalPlain"):
        parts.append(data["additionalPlain"].strip())
    return ExtractedJob(
        title=(data.get("text") or "").strip(),
        company=company.replace("-", " ").title(),
        description="\n\n".join(p for p in parts if p),
    )


_ATS_EXTRACTORS = (_extract_workable, _extract_greenhouse, _extract_lever)


# ----- JSON-LD JobPosting (schema.org) -----
#
# Many large company career sites (KPMG, Microsoft, banks, etc.) embed
# schema.org JobPosting structured data in <script type="application/ld+json">
# blocks. This is more reliable than Trafilatura's heuristic text
# extraction because the fields are explicit. Runs AFTER ATS-specific
# extractors (which return even cleaner data) but BEFORE generic
# Trafilatura.

_JSONLD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def _extract_from_jsonld(html: str) -> ExtractedJob | None:
    """Find a JSON-LD JobPosting in the HTML and convert to ExtractedJob.

    Handles two shapes:
      - The block itself is a JobPosting object.
      - The block is an array (e.g., BreadcrumbList + JobPosting); we
        scan for the first object with @type == "JobPosting".
    Returns None if no JobPosting block is found or if parsing fails.
    """
    for raw in _JSONLD_RE.findall(html):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            t = entry.get("@type")
            if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                return _job_posting_to_extracted(entry)
    return None


def _job_posting_to_extracted(entry: dict) -> ExtractedJob:
    title = (entry.get("title") or "").strip()
    org = entry.get("hiringOrganization") or {}
    if isinstance(org, dict):
        company = (org.get("name") or "").strip()
    elif isinstance(org, str):
        company = org.strip()
    else:
        company = ""
    description = _strip_html(entry.get("description") or "")
    return ExtractedJob(
        title=title, company=company, description=description.strip()
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
