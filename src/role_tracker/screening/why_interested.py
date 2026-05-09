"""Help with the "Why are you interested in this role?" screening
answer.

Two operations, both single-shot Haiku calls:

1. **JD highlights** — surfaces 4-5 short factual bullets about what's
   distinctive in the job description: notable team / product / domain
   / stated requirement / location / comp / tech. The user reads
   these as research material and then writes their own answer.

2. **Polish** — fixes grammar in whatever the user actually wrote.
   No idea-injection. Same length, same meaning, same voice.

Design note: the highlights call deliberately does NOT receive the
resume. It is research about the JOB, not a fit assessment of the
candidate. The motivation that goes into the user's final answer
must come from the user reading the highlights and recognising what
genuinely matters to *them*. We are not ghostwriting motivation.

The previous "generate the full why-interested answer" capability
was removed in May 2026 because the output looked like authentic
personal motivation but wasn't, and that's the one thing recruiters
actually probe for. See docs/HANDBOOK.md for the design rationale.
"""

from __future__ import annotations

import json

from anthropic import Anthropic

from role_tracker.jobs.models import JobPosting

# Use the cheaper model — these are one-shot, no agentic loop.
_MODEL = "claude-haiku-4-5-20251001"


# ----- JD highlights -----------------------------------------------------


_HIGHLIGHTS_SYSTEM_PROMPT = """\
You read a job description and produce a short list of factual,
distinctive points about the role. The user will use your output as
research material when writing their own "Why are you interested in
this role?" answer.

Output exactly one JSON object, no surrounding text, no markdown,
no code fences. Schema:

{
  "highlights": [
    "string",
    "string",
    ...
  ]
}

Each entry is one short sentence (10-20 words). Aim for 4-5 entries
total. Pick what's actually distinctive about THIS role/company.

GOOD highlights (specific, factual, surfaces something the user
might find genuinely interesting):
- "Risk team specifically builds fraud-detection ML, not generic data work"
- "'Production ML experience' stated as required — past prototype phase"
- "Hybrid in Toronto, two days in office per week"
- "Salary range $180-220k stated openly"
- "Tech stack mentions PyTorch + distributed training (Spark or Beam)"

BAD highlights (generic, fluff, editorial):
- "This is a great opportunity at a fast-growing company"
- "They value innovation and collaboration"
- "Excellent benefits and culture"

HARD RULES
- Stick to facts the JD actually states. Never invent.
- Empty list is acceptable if the JD truly says nothing distinctive
  (very rare, but better than padding).
- Don't editorialise ("amazing role", "great opportunity"). Stay neutral.
- Don't suggest motivation ("you'd love working here"). Just surface
  facts; the user picks what resonates.
- Refer to the company by name, not "the company".
- No em-dashes. Use commas or periods.
"""


class HighlightsError(Exception):
    """Raised when the model returns text that isn't valid JSON or
    doesn't match the expected schema."""


def generate_jd_highlights(
    *,
    job: JobPosting,
    client: Anthropic,
    model: str = _MODEL,
) -> list[str]:
    """Return 4-5 short factual bullets about what's distinctive in the
    JD.

    Resume is NOT passed in — this is research about the job, not a
    fit assessment. See module docstring for the rationale.
    """
    user_message = (
        "<job_description>\n"
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location}\n\n"
        f"{job.description}\n"
        "</job_description>\n\n"
        "Return the JSON object now."
    )
    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=_HIGHLIGHTS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]
    text = "".join(parts).strip()
    return _parse_highlights(text)


def _parse_highlights(text: str) -> list[str]:
    """Coerce the model's reply into a list of highlight strings.

    Tolerates ```json fences the model occasionally adds.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -len("```")]
        cleaned = cleaned.strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HighlightsError(f"model did not return JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise HighlightsError(
            f"expected a JSON object, got {type(payload).__name__}"
        )

    highlights = payload.get("highlights")
    if not isinstance(highlights, list):
        raise HighlightsError(
            "JSON object missing a 'highlights' list"
        )
    out: list[str] = []
    for item in highlights:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


# ----- Polish ------------------------------------------------------------


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
