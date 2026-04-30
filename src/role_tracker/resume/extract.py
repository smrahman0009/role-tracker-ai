"""Pull contact info out of a parsed resume's text.

Used by the resume-upload route to pre-fill the user's profile so a
fresh user doesn't have to retype name / email / phone / LinkedIn /
GitHub when they already exist in the PDF they just uploaded.

Pure regex / heuristic — no LLM call. The resume header is the most
predictably-formatted part of any resume so the false-positive rate
is low. Anything we can't extract cleanly we leave blank, and the
frontend renders the field empty for the user to fill in.
"""

from __future__ import annotations

import re

from pydantic import BaseModel


class ExtractedContact(BaseModel):
    """All fields default to empty so callers can patch the profile
    with model_dump(exclude_defaults=True) and only overwrite what we
    actually found."""

    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    github_url: str = ""

    def populated_fields(self) -> list[str]:
        return [k for k, v in self.model_dump().items() if v]


# RFC-5322-ish but pragmatic. Will match anything that looks like an
# email and isn't trying very hard to validate.
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")

# North American + international phone numbers in common surface forms:
#   +1 (555) 123-4567, 555-123-4567, 555.123.4567, +44 20 7946 0958
# Requires at least 10 digits in total to avoid matching room numbers
# / years / postal codes.
_PHONE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?"
    r"(?:\(\d{2,4}\)|\d{2,4})[\s.-]?"
    r"\d{3,4}[\s.-]?\d{3,4}(?!\d)"
)

# Captures the slug after /in/. Tolerates http/https, www, trailing slash.
_LINKEDIN = re.compile(
    r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?",
    re.IGNORECASE,
)

# GitHub user/org URL. We don't try to distinguish a profile from a repo;
# either is fine in the profile field.
_GITHUB = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9][A-Za-z0-9_.-]*/?",
    re.IGNORECASE,
)


def extract_contact_info(text: str) -> ExtractedContact:
    """Run the heuristics over a resume's plain text."""
    return ExtractedContact(
        name=_extract_name(text),
        email=_extract_email(text),
        phone=_extract_phone(text),
        linkedin_url=_extract_linkedin(text),
        github_url=_extract_github(text),
    )


# ----- individual extractors -----


def _extract_email(text: str) -> str:
    m = _EMAIL.search(text)
    return m.group(0) if m else ""


def _extract_phone(text: str) -> str:
    """Return the first phone-shaped match with at least 10 digits."""
    for match in _PHONE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if 10 <= len(digits) <= 15:
            return match.group(0).strip()
    return ""


def _extract_linkedin(text: str) -> str:
    m = _LINKEDIN.search(text)
    if not m:
        return ""
    url = m.group(0).rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def _extract_github(text: str) -> str:
    m = _GITHUB.search(text)
    if not m:
        return ""
    url = m.group(0).rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def _extract_name(text: str) -> str:
    """First plausible name-shaped line at the top of the resume.

    Heuristic: first non-empty line that's 2-5 words, < 60 chars, and
    contains no digits / @ / colons / common header keywords. Most
    resumes put the candidate's name on line 1; this catches that
    without false-matching section headings like "Professional Summary".
    """
    bad_words = {
        "summary",
        "experience",
        "education",
        "skills",
        "objective",
        "profile",
        "contact",
        "resume",
        "curriculum",
        "vitae",
    }
    for raw in text.splitlines()[:10]:
        line = raw.strip()
        if not line or len(line) > 60:
            continue
        if any(c in line for c in "@:|/\\"):
            continue
        if any(ch.isdigit() for ch in line):
            continue
        words = line.split()
        if not (2 <= len(words) <= 5):
            continue
        if any(w.lower().strip(",.") in bad_words for w in words):
            continue
        if not all(w[0].isalpha() for w in words):
            continue
        # Names are conventionally title case ("Jane Doe"), upper case
        # ("JANE DOE"), or mixed ("Jane O'Hara"). Reject lines with any
        # word that starts lowercase — that catches sentences like
        # "I'm a data scientist...".
        if any(w[0].islower() for w in words):
            continue
        # Reject lines that include sentence punctuation — names don't
        # end with periods (titles like "Jr.") or contain commas mid-line
        # in this form.
        if any(p in line for p in ("...", ",", ";", "!", "?")):
            continue
        return line
    return ""
