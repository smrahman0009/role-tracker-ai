"""Tests for url_extract — focused on the ATS-specific JSON extractors.

The Trafilatura fallback path is exercised by tests/api/test_jobs.py
where the route is mocked at the function level. Here we verify the
ATS path directly: pattern matching + JSON parsing + field stitching.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from role_tracker.jobs.url_extract import extract_job_from_url


class _StubClient:
    """Mocks httpx.Client.get to return canned JSON for known URLs."""

    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        # responses: { url: {"status": int, "json": ..., "text": str} }
        self._responses = responses
        self.requested: list[str] = []

    def get(self, url: str, **_kwargs: Any) -> httpx.Response:
        self.requested.append(url)
        spec = self._responses.get(url)
        request = httpx.Request("GET", url)
        if spec is None:
            response = httpx.Response(404, text="not found")
        elif spec.get("json") is not None:
            # Pass `json` only; `text` would zero out the body.
            response = httpx.Response(spec.get("status", 200), json=spec["json"])
        else:
            response = httpx.Response(
                spec.get("status", 200), text=spec.get("text", "")
            )
        # raise_for_status() needs the request attached.
        response.request = request
        return response

    def close(self) -> None:  # pragma: no cover — protocol completeness
        pass


def test_workable_url_uses_json_api() -> None:
    """apply.workable.com/{tenant}/j/{shortcode} → JSON endpoint hit."""
    api_url = (
        "https://apply.workable.com/api/v1/accounts/liferaft/jobs/8B6B0E4580"
    )
    client = _StubClient(
        {
            api_url: {
                "json": {
                    "title": "Director, Finance",
                    "location": {
                        "city": "Halifax",
                        "country": "Canada",
                        "region": "NS",
                    },
                    "description": (
                        "<p>Liferaft is hiring a finance director.</p>"
                    ),
                    "requirements": "<ul><li>5+ years exp</li></ul>",
                    "benefits": "<p>Healthcare, equity</p>",
                }
            }
        }
    )
    out = extract_job_from_url(
        "https://apply.workable.com/liferaft/j/8B6B0E4580/",
        http_client=client,
    )
    assert out.title == "Director, Finance"
    assert out.company == "Liferaft"
    # Description, requirements, and benefits all present, HTML stripped.
    assert "Liferaft is hiring a finance director." in out.description
    assert "5+ years exp" in out.description
    assert "Healthcare, equity" in out.description
    assert "<" not in out.description  # tags stripped


def test_workable_falls_back_when_json_api_404s() -> None:
    """If the API endpoint 404s for some reason, the extractor returns
    None and we fall through to the Trafilatura HTML path. The HTML
    path also fails for SPAs (no content), so the final ExtractedJob
    is empty — handled gracefully, not crashed."""
    client = _StubClient({})  # no responses → everything 404s
    out = extract_job_from_url(
        "https://apply.workable.com/liferaft/j/UNKNOWN/",
        http_client=client,
    )
    # Empty fields, no exception.
    assert out.title == ""
    assert out.company == ""
    assert out.description == ""


def test_greenhouse_url_uses_boards_api() -> None:
    """boards.greenhouse.io/{board}/jobs/{id} → boards-api.greenhouse.io"""
    api_url = "https://boards-api.greenhouse.io/v1/boards/acme/jobs/1234567"
    client = _StubClient(
        {
            api_url: {
                "json": {
                    "title": "Senior ML Engineer",
                    "content": (
                        "<p>Build production recommendation systems "
                        "at scale. 5+ years of experience required.</p>"
                    ),
                }
            }
        }
    )
    out = extract_job_from_url(
        "https://boards.greenhouse.io/acme/jobs/1234567",
        http_client=client,
    )
    assert out.title == "Senior ML Engineer"
    assert out.company == "Acme"
    assert "Build production recommendation systems" in out.description
    assert "<" not in out.description


def test_lever_url_uses_lever_api() -> None:
    """jobs.lever.co/{company}/{id} → api.lever.co/v0/postings/..."""
    api_url = "https://api.lever.co/v0/postings/acme/abc-123"
    client = _StubClient(
        {
            api_url: {
                "json": {
                    "text": "Staff Software Engineer",
                    "descriptionPlain": (
                        "Join us building the next-gen platform."
                    ),
                    "lists": [
                        {
                            "text": "What you'll do",
                            "content": "<li>Ship features</li>",
                        },
                        {
                            "text": "Requirements",
                            "content": "<li>5+ years backend</li>",
                        },
                    ],
                    "additionalPlain": "We offer competitive comp.",
                }
            }
        }
    )
    out = extract_job_from_url(
        "https://jobs.lever.co/acme/abc-123",
        http_client=client,
    )
    assert out.title == "Staff Software Engineer"
    assert out.company == "Acme"
    assert "next-gen platform" in out.description
    assert "What you'll do" in out.description
    assert "Ship features" in out.description
    assert "5+ years backend" in out.description
    assert "competitive comp" in out.description


def test_non_ats_url_falls_through_to_trafilatura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A URL that doesn't match any ATS pattern goes through the
    Trafilatura path — verified by ensuring the ATS extractors are NOT
    consulted (the stub client only has a generic HTML response)."""

    html_text = (
        "<html><head><title>Acme — ML Engineer</title>"
        "<meta property='og:site_name' content='Acme Careers'></head>"
        "<body><article>"
        + ("<p>Build production ML systems for the recommendations team. "
           "5+ years experience required. Strong Python and PyTorch.</p>"
           * 8)
        + "</article></body></html>"
    )
    client = _StubClient(
        {
            "https://acme.example.com/careers/job/42": {
                "text": html_text,
                "json": None,
            }
        }
    )
    out = extract_job_from_url(
        "https://acme.example.com/careers/job/42",
        http_client=client,
    )
    # Trafilatura found something in the article body.
    assert "production ML systems" in out.description
    assert out.title  # extracted from <title>


def test_workable_url_pattern_with_trailing_slash() -> None:
    """The URL the user reported had a trailing slash; pattern must
    handle both forms."""
    api_url = (
        "https://apply.workable.com/api/v1/accounts/liferaft/jobs/8B6B0E4580"
    )
    client = _StubClient(
        {api_url: {"json": {"title": "Test", "description": "Body" * 20}}}
    )
    # With trailing slash:
    out = extract_job_from_url(
        "https://apply.workable.com/liferaft/j/8B6B0E4580/",
        http_client=client,
    )
    assert out.title == "Test"
    # Without trailing slash:
    out = extract_job_from_url(
        "https://apply.workable.com/liferaft/j/8B6B0E4580",
        http_client=client,
    )
    assert out.title == "Test"


# ----- JSON-LD JobPosting (schema.org) -----


_JSONLD_HTML = '''<!doctype html><html><head>
<title>Senior Consultant — KPMG</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "Senior Consultant, ML/AI Engineer",
  "hiringOrganization": {"@type": "Organization", "name": "KPMG"},
  "description": "<p>At KPMG, you&rsquo;ll join a team.</p><ul><li>Build ML systems</li><li>Mentor juniors</li></ul>"
}
</script>
</head><body>SPA shell</body></html>'''


def test_jsonld_jobposting_extraction() -> None:
    """Pages that embed schema.org JobPosting structured data should be
    extracted via that block, not via Trafilatura's heuristic."""
    client = _StubClient(
        {"https://careers.kpmg.ca/jobs/123": {"text": _JSONLD_HTML}}
    )
    out = extract_job_from_url(
        "https://careers.kpmg.ca/jobs/123", http_client=client
    )
    assert out.title == "Senior Consultant, ML/AI Engineer"
    assert out.company == "KPMG"
    # Entities decoded.
    assert "you’ll" in out.description
    # Tags stripped, list items preserved as bullets.
    assert "Build ML systems" in out.description
    assert "Mentor juniors" in out.description
    assert "<" not in out.description


def test_jsonld_array_with_breadcrumb_and_jobposting() -> None:
    """Some sites ship JSON-LD as an array of multiple entities. We
    pick the JobPosting out of the array."""
    html = (
        '<script type="application/ld+json">'
        '[{"@type":"BreadcrumbList","itemListElement":[]},'
        ' {"@type":"JobPosting","title":"Backend Engineer",'
        '  "hiringOrganization":{"name":"Acme"},'
        '  "description":"<p>Build distributed systems.</p>"}]'
        "</script>"
    )
    client = _StubClient({"https://acme.example/jobs/9": {"text": html}})
    out = extract_job_from_url(
        "https://acme.example/jobs/9", http_client=client
    )
    assert out.title == "Backend Engineer"
    assert out.company == "Acme"
    assert "Build distributed systems" in out.description


def test_jsonld_runs_before_trafilatura_fallback() -> None:
    """When both JSON-LD and Trafilatura-extractable content are
    present, the JSON-LD wins because it's structured and reliable."""
    html = (
        '<script type="application/ld+json">'
        '{"@type":"JobPosting","title":"FromJsonLd",'
        '"hiringOrganization":{"name":"Acme"},'
        '"description":"<p>The structured JD has 60+ chars of body content here.</p>"}'
        "</script>"
        "<article>"
        + ("<p>Trafilatura would find this article body too. </p>" * 10)
        + "</article>"
    )
    client = _StubClient({"https://x/jobs/1": {"text": html}})
    out = extract_job_from_url("https://x/jobs/1", http_client=client)
    assert out.title == "FromJsonLd"
    assert "structured JD" in out.description
