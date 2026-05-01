"""Render-time substitution of a cover letter's contact header.

The agent generates the contact header (name + phone/email/links) as
part of the letter body and we store the whole thing as one blob of
markdown text. That means changes to the user's profile (toggle
LinkedIn off, fix a typo in the phone number, add a portfolio URL)
don't propagate to letters that have already been generated.

Treating the header as a *render-time view of the profile* fixes that:
on every read — whether the JSON Letter response, a PDF download, or
a DOCX download — we strip the stored header and substitute the
current `user.contact_header()`. Toggle a field in Settings, refresh,
the change shows up everywhere.

Two safety rails so we never overwrite explicit user work:

1. Letters with `edited_by_user=True` are NOT substituted. If the user
   manually edited the letter (Edit -> Save), we treat their text as
   sacrosanct — they may have customised the header on purpose.
2. We only substitute when paragraph 1 of the stored text actually
   looks like the agent-generated header (matches `**{user.name}**`
   on its first line). If it doesn't — because of an unusual layout
   or because the user removed the header — we prepend the fresh
   header rather than overwriting an unrelated paragraph.
"""

from __future__ import annotations

from role_tracker.users.models import UserProfile


def with_current_header(
    *,
    text: str,
    user: UserProfile,
    edited_by_user: bool,
) -> str:
    """Return the letter text with the contact header pulled from the
    user's *current* profile, unless the letter has been manually edited.

    Args:
        text: The stored letter text.
        user: The user whose profile drives the live header.
        edited_by_user: If True, the user has manually edited this version
            and we leave the text untouched.
    """
    if edited_by_user:
        return text

    if not user.name.strip():
        # Placeholder / unconfigured profile — no real header to emit.
        # Leave the stored text alone rather than prepend `****` (which
        # is what contact_header() returns when name is blank).
        return text

    fresh_header = user.contact_header().strip()
    if not fresh_header:
        return text

    paragraphs = text.split("\n\n", 1)
    body = paragraphs[1] if len(paragraphs) == 2 else text

    if _looks_like_header(paragraphs[0], user):
        return f"{fresh_header}\n\n{body.lstrip()}"

    # First paragraph isn't a recognisable header — prepend without
    # overwriting whatever's there.
    return f"{fresh_header}\n\n{text.lstrip()}"


def _looks_like_header(paragraph: str, user: UserProfile) -> bool:
    """The agent's header always starts with `**{user.name}**` on
    line 1. If we see that pattern, treat the paragraph as the header."""
    if not user.name.strip():
        return False
    first_line = paragraph.split("\n", 1)[0].strip()
    return first_line == f"**{user.name.strip()}**"
