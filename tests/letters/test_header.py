"""Tests for the live-header substitution helper.

The function takes the stored letter text and the user's *current*
profile, and returns the letter with paragraph 1 replaced by the
fresh contact header — unless the user has manually edited the letter
(`edited_by_user=True`), in which case we leave their text alone.
"""

from __future__ import annotations

from pathlib import Path

from role_tracker.letters.header import with_current_header
from role_tracker.users.models import UserProfile


def _user(**overrides: object) -> UserProfile:
    base = dict(
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
    base.update(overrides)
    return UserProfile(**base)  # type: ignore[arg-type]


_LETTER_WITH_OLD_HEADER = (
    "**Alice Doe**\n"
    "+1 555 0100 | alice@example.com | Halifax, NS\n"  # no LinkedIn
    "\n\n"
    "Dear Acme Team,\n\n"
    "Body paragraph survives.\n\n"
    "Best,\nAlice"
)


def test_substitutes_header_when_user_has_added_linkedin() -> None:
    """The user enabled LinkedIn after generation; the live header should
    now include it on every read."""
    out = with_current_header(
        text=_LETTER_WITH_OLD_HEADER,
        user=_user(),
        edited_by_user=False,
    )
    assert "linkedin.com/in/alice-doe" in out
    assert "Body paragraph survives." in out


def test_skipped_when_letter_was_manually_edited() -> None:
    """User-edited letters stay exactly as the user wrote them — even if
    Settings would now suggest a different header."""
    out = with_current_header(
        text=_LETTER_WITH_OLD_HEADER,
        user=_user(),
        edited_by_user=True,
    )
    assert out == _LETTER_WITH_OLD_HEADER


def test_substitutes_when_user_disables_a_field() -> None:
    """Toggling show_phone_in_header off should drop the phone from the
    rendered header on the next read."""
    out = with_current_header(
        text=_LETTER_WITH_OLD_HEADER,
        user=_user(show_phone_in_header=False),
        edited_by_user=False,
    )
    assert "+1 555 0100" not in out
    assert "alice@example.com" in out


def test_prepends_when_first_paragraph_does_not_look_like_header() -> None:
    """Defensive: if the stored text doesn't start with a recognisable
    header (e.g. the user removed it during a previous edit but the
    edited_by_user flag was somehow lost), prepend the fresh header
    rather than overwriting an unrelated paragraph."""
    text_without_header = "Dear Acme Team,\n\nBody paragraph.\n\nBest,\nAlice"
    out = with_current_header(
        text=text_without_header,
        user=_user(),
        edited_by_user=False,
    )
    assert out.startswith("**Alice Doe**")
    assert "Dear Acme Team," in out
    assert "Body paragraph." in out


def test_returns_unchanged_when_profile_yields_empty_header() -> None:
    """A blank-name profile (the placeholder we use when no profile
    exists yet) should leave the stored text alone rather than emit
    an empty paragraph at the top."""
    blank = UserProfile(
        id="alice",
        name="",
        resume_path=Path(""),
        queries=[],
    )
    out = with_current_header(
        text=_LETTER_WITH_OLD_HEADER,
        user=blank,
        edited_by_user=False,
    )
    assert out == _LETTER_WITH_OLD_HEADER


def test_multi_line_header_with_links_is_preserved() -> None:
    """The full three-line header (name / contacts / links) should be
    written as a single paragraph with single-newline soft breaks."""
    out = with_current_header(
        text=_LETTER_WITH_OLD_HEADER,
        user=_user(github_url="https://github.com/alice"),
        edited_by_user=False,
    )
    # Header is paragraph 1, body is paragraph 2+.
    head, _ = out.split("\n\n", 1)
    lines = head.split("\n")
    assert lines[0] == "**Alice Doe**"
    assert "alice@example.com" in lines[1]
    assert "[LinkedIn]" in lines[2] and "[GitHub]" in lines[2]
