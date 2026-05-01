"""Tests for refine_cover_letter — focused on the header-replacement fix.

The agent saw both the fresh header_block (from current profile) and the
previous letter's stale header. It tended to preserve the old one. We now
deterministically substitute the current profile's contact_header() onto
the agent's output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from role_tracker.cover_letter.refine import refine_cover_letter
from role_tracker.jobs.models import JobPosting
from role_tracker.users.models import UserProfile


def _user_with_linkedin() -> UserProfile:
    """Profile that has LinkedIn enabled — the post-Settings-change state."""
    return UserProfile(
        id="alice",
        name="Alice Doe",
        email="alice@example.com",
        phone="+1 555 0100",
        city="Halifax, NS",
        linkedin_url="https://linkedin.com/in/alice-doe",
        show_linkedin_in_header=True,
        resume_path=Path("data/resumes/alice.pdf"),
        queries=[],
    )


def _job() -> JobPosting:
    return JobPosting(
        id="j1",
        title="ML Engineer",
        company="Acme",
        location="Halifax, Canada",
        description="Build models.",
        url="https://example.com",
        posted_at="2026-04-28T00:00:00Z",
        source="jsearch",
        publisher="Acme Careers",
    )


def _stub_client(agent_output: str) -> Any:
    """Build a minimal stand-in for an Anthropic client that returns
    `agent_output` from messages.create()."""

    class _Block:
        type = "text"

        def __init__(self, text: str) -> None:
            self.text = text

    class _Response:
        def __init__(self, text: str) -> None:
            self.content = [_Block(text)]

    class _Messages:
        def create(self, **_kwargs: Any) -> _Response:  # noqa: D401
            return _Response(agent_output)

    class _Client:
        messages = _Messages()

    return _Client()


def test_refine_substitutes_fresh_header_when_agent_keeps_stale_one() -> None:
    """Agent returns text with the OLD header (no LinkedIn). After refine,
    the output should reflect the CURRENT profile (with LinkedIn)."""
    user = _user_with_linkedin()
    stale_letter = (
        "**Alice Doe**\n"
        "+1 555 0100 | alice@example.com | Halifax, NS\n\n"  # no LinkedIn
        "Dear team,\n\n"
        "I am applying because of the role's focus on production ML.\n\n"
        "Best,\nAlice"
    )

    revised = refine_cover_letter(
        user=user,
        resume_text="Built ML systems at scale.",
        job=_job(),
        previous_letter=stale_letter,
        previous_strategy={
            "fit_assessment": "MEDIUM",
            "narrative_angle": "ML ops",
            "primary_project": "X",
            "secondary_project": None,
        },
        feedback="Make the opening punchier.",
        client=_stub_client(stale_letter),  # agent echoes the old letter back
    )

    # Fresh header (with LinkedIn) replaces the stale header.
    assert "linkedin.com/in/alice-doe" in revised
    assert "[LinkedIn](https://linkedin.com/in/alice-doe)" in revised


def test_refine_preserves_body_after_header_substitution() -> None:
    """The substitution should only touch paragraph 1 — the body survives."""
    user = _user_with_linkedin()
    agent_output = (
        "**Alice Doe**\n"
        "old contact line\n\n"
        "Dear team,\n\n"
        "Body paragraph that the agent crafted.\n\n"
        "Best,\nAlice"
    )

    revised = refine_cover_letter(
        user=user,
        resume_text="x",
        job=_job(),
        previous_letter="x",
        previous_strategy={"fit_assessment": "HIGH"},
        feedback="x",
        client=_stub_client(agent_output),
    )
    assert "Body paragraph that the agent crafted." in revised
    assert "Dear team," in revised
    assert "Best,\nAlice" in revised


def test_refine_handles_agent_output_without_paragraph_break() -> None:
    """If the agent forgot the blank line after the header, we still prepend
    a fresh header rather than silently dropping the substitution."""
    user = _user_with_linkedin()
    agent_output = "Dear team,\n\nBody text without a header at all."

    revised = refine_cover_letter(
        user=user,
        resume_text="x",
        job=_job(),
        previous_letter="x",
        previous_strategy={"fit_assessment": "HIGH"},
        feedback="x",
        client=_stub_client(agent_output),
    )
    # Fresh header is at the top.
    assert revised.startswith("**Alice Doe**")
    assert "linkedin.com" in revised
    # Body content survives.
    assert "Body text without a header at all." in revised
