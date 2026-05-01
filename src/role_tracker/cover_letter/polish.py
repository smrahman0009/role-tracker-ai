"""Lightweight grammar/clarity polish for a cover letter draft.

Distinct from refine.py — refine takes user feedback and rewrites
substantively (creates a new version, runs through the critique
loop, ~$0.05). Polish is the cheap counterpart: a single Haiku call
that fixes grammar, awkward phrasing, and typos in the user's edits
without changing meaning, length, or structure (~$0.005, ~3s).

The frontend wires this into the existing Edit textarea so the
user's workflow is: click Edit → tweak words → Polish → Save edit.
Polish does NOT save a new version itself; the existing manual-edit
endpoint does that when the user clicks Save.
"""

from __future__ import annotations

from anthropic import Anthropic

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """\
You are a grammar and clarity editor for a cover letter draft. The
user has manually edited an existing letter and wants you to clean
up grammar, awkward phrasing, and typos — nothing else.

HARD RULES (these are non-negotiable)
- Preserve the meaning. Do not add new ideas, examples, or claims.
  If the user removed a sentence, leave it removed.
- Preserve the length. Output should be within ±20 words of the input.
- Preserve the structure: every paragraph break (blank line between
  paragraphs) stays a paragraph break. Single-newline soft breaks in
  the contact header stay single-newline soft breaks.
- Preserve `**bold**` markers exactly where they are. Don't add or
  remove emphasis.
- Preserve `[label](url)` markdown link syntax exactly. Don't unwrap
  or reformat URLs.
- Preserve voice. First-person stays first-person. Don't make a
  direct sentence sound more "professional" if it's already clear.
- Do NOT introduce LLM clichés (thrilled, excited to apply, deeply
  passionate, leverage, delve, synergy, "I am drawn to", "at the
  intersection of", "navigate" as a verb).
- Output the corrected letter ONLY. No preamble, no explanation, no
  markdown code fences, no quotes around the output.

If the input is already grammatically clean, return it unchanged.
"""


def polish_cover_letter(*, text: str, client: Anthropic, model: str = _MODEL) -> str:
    """Return the user's edited letter with grammar / clarity issues fixed."""
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]
    return "".join(parts).strip()
