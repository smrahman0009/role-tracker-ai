"""Generate the "Why are you interested in this role?" answer.

This is the screening question that appears on almost every apply
form (Greenhouse, Lever, Workday, custom employer ATSes). It's
distinct from the cover letter — typically 2-3 sentences, more
focused on company-specific specifics, often capped at 500 chars
in the form's text input.

One Claude call, no critique loop. ~$0.01 per generation.
"""

from __future__ import annotations

from anthropic import Anthropic

from role_tracker.jobs.models import JobPosting

# Use the cheaper model — this is a one-shot, no agentic loop.
_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """\
You write the "Why are you interested in this role?" answer that
appears on almost every job application form. Keep it tight: 2-3
sentences, first-person, direct, grounded in the candidate's actual
resume.

HARD RULES
- Reference 1-2 specific things from the job description (the team,
  the product, a technology, a domain, a stated mission). Generic
  "your innovative culture" is a fail.
- Anchor your reasoning in something the candidate has actually done
  (a project, a domain of experience, a skill demonstrated on the
  resume). No inventing experience.
- No LLM clichés: never use "thrilled", "excited to apply", "deeply
  passionate", "I am drawn to", "synergy", "leverage", "delve".
- No fluff: skip introductions, sign-offs, restating the job title.
- Stay under the target word count. Going over is worse than going under.
- Output the answer text only. No preamble, no quotes, no markdown.
"""


def generate_why_interested(
    *,
    job: JobPosting,
    resume_text: str,
    target_words: int,
    client: Anthropic,
    model: str = _MODEL,
) -> str:
    """Return a 2-3 sentence "why interested" answer as plain text."""
    user_message = (
        f"<target_words>{target_words}</target_words>\n\n"
        "<job_description>\n"
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location}\n\n"
        f"{job.description}\n"
        "</job_description>\n\n"
        "<resume>\n"
        f"{resume_text}\n"
        "</resume>\n\n"
        f"Write the answer in roughly {target_words} words."
    )

    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]
    return "".join(parts).strip()
