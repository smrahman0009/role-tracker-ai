"""Polish helper for the "Why are you interested in this role?"
screening answer.

The dialog used to *generate* this answer end-to-end with Claude
(resume + JD → 2-3 sentence motivation paragraph). That generator
was removed in May 2026 because the output looked authentic but
wasn't, and "why are you interested?" is the one recruiter question
specifically about authenticity.

What's left here is just a grammar-fix pass: the user writes their
own answer in the dialog, clicks Polish, gets back a cleaned
version with the same meaning, length, and voice. This is
defensible AI assist (copy-edit, not ghostwrite).
"""

from __future__ import annotations

from anthropic import Anthropic

# Cheap, fast — single-shot, no agentic loop.
_MODEL = "claude-haiku-4-5-20251001"


_POLISH_SYSTEM = """\
You are a grammar and clarity editor. The user has written or edited
a short answer to a job-application screening question. Your only job
is to fix grammar, awkward phrasing, and obvious typos.

HARD RULES
- Preserve the meaning. Do not add new ideas, examples, or claims.
- Preserve the length. Output should be within ±10 words of the input.
- Preserve the voice. First-person stays first-person. Don't rewrite
  it to sound more "professional" if the user's voice is direct.
- Do not introduce LLM clichés (thrilled, excited, passionate about,
  leverage, delve, synergy).
- Do not add quotes, headings, or sign-offs.
- Output the corrected text only — no preamble, no explanation.

If the input is already grammatically clean, return it unchanged.
"""


def polish_why_interested(
    *,
    text: str,
    client: Anthropic,
    model: str = _MODEL,
) -> str:
    """Fix grammar/clarity in an existing answer. Same length, same meaning."""
    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=_POLISH_SYSTEM,
        messages=[{"role": "user", "content": text}],
    )
    parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]
    return "".join(parts).strip()
