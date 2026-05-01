"""Letter refinement — revise an existing letter based on user feedback.

Distinct from the full agent run because:
- The strategy is already committed and stays locked.
- Resume content has already been chosen for the primary/secondary projects.
- The structural decisions (3 paragraphs, hook → body → close) have been made.

So refinement is a single Sonnet call with a refine-specific system prompt,
not a full agent loop. Faster (~10-15 seconds vs 30-60), cheaper, and the
output is constrained to "same letter, different prose."

The previous letter, the committed strategy, and the user's feedback are
all included in the user message. The system prompt explicitly says: "you
may not change the strategy, you may not introduce new projects, you may
not invent claims."
"""

from __future__ import annotations

from anthropic import Anthropic

from role_tracker.jobs.models import JobPosting
from role_tracker.users.models import UserProfile

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048

REFINE_SYSTEM_PROMPT = """\
You are revising an existing cover letter based on user feedback. The
candidate already approved the overall strategy of this letter — the
primary project, the narrative angle, and the fit assessment are LOCKED.
Your job is to apply the feedback while keeping the strategy intact.

WHAT YOU MAY CHANGE:
- Prose, sentence structure, and voice
- Length (within the 280-420 word range)
- Emphasis between sentences (lead with X instead of Y)
- Tone (more technical, less formal, etc.)
- Specific phrasings the user disliked

WHAT YOU MAY NOT CHANGE:
- The primary project (the spine of the letter)
- The secondary project, if one exists
- The narrative angle / through-line
- The fit assessment
- Any factual claims — these must still trace to the resume

GREETING:
- Use "Dear {Company} Team," — substitute the actual company name from
  the job (e.g., "Dear Acme Team,"). If awkward (company contains
  "Inc." / "Corporation" / commas / already ends in "Team"), use
  "Dear Hiring Team,". Never "Hello," or "To whom it may concern,".
- If the previous letter has a different greeting, replace it.

If the user's feedback implies a STRATEGY change ("focus on the audio ML
work instead of NLP", "switch the angle to recsys"), do NOT honour it.
Produce a revision that addresses the feedback as best you can within
the locked strategy. If you cannot meaningfully address the feedback
without changing the strategy, return a letter very close to the
original and explain in a single line at the end (commented `<!-- -->`).

GROUNDING:
- Every factual claim must come from the resume content provided.
- Do not introduce new claims.
- Hedge phrases like "I'm familiar with" or "I've informally applied"
  count as factual claims and must be backed by the resume.

BANNED LANGUAGE (do not use):
- Em dashes in prose. Use commas or periods.
- LLM tell-tales: leverage (verb), navigate (verb), delve, pivotal,
  realm, showcase, cutting-edge, seamless, unleash, unlock,
  "at the intersection of", "passionate about".
- Cover-letter clichés: "I am writing to express", "I am excited/
  thrilled to apply", "I would be a great fit", "team player",
  "self-starter", "hit the ground running", "perfect candidate".

OUTPUT:
- Return ONLY the revised letter text, including the header block,
  greeting, body paragraphs, sign-off, and name.
- No preamble, no commentary, no markdown fences.
- 280-420 words total.
"""


def refine_cover_letter(
    *,
    user: UserProfile,
    resume_text: str,
    job: JobPosting,
    previous_letter: str,
    previous_strategy: dict,
    feedback: str,
    client: Anthropic,
    model: str = MODEL,
) -> str:
    """Run a single Sonnet call to revise the previous letter.

    Returns the revised letter text. Does NOT run critique — the strategy
    was already validated when the original was generated, so revisions
    that stay within the strategy should remain rubric-acceptable. If
    quality regresses across many refine rounds, we can add critique
    here in a later iteration.
    """
    user_message = (
        "Revise the cover letter below based on the user's feedback. "
        "Keep the committed strategy intact.\n\n"
        f"<resume>\n{resume_text.strip()}\n</resume>\n\n"
        f"<job>\n"
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location}\n\n"
        f"Description:\n{job.description.strip()}\n"
        f"</job>\n\n"
        f"<committed_strategy>\n"
        f"fit_assessment: {previous_strategy.get('fit_assessment', '?')}\n"
        f"narrative_angle: {previous_strategy.get('narrative_angle', '?')}\n"
        f"primary_project: {previous_strategy.get('primary_project', '?')}\n"
        f"secondary_project: "
        f"{previous_strategy.get('secondary_project') or '(none)'}\n"
        f"</committed_strategy>\n\n"
        f"<header_block>\n{user.contact_header()}\n</header_block>\n\n"
        f"<previous_letter>\n{previous_letter.strip()}\n</previous_letter>\n\n"
        f"<feedback>\n{feedback.strip()}\n</feedback>\n\n"
        "Return the revised letter text only."
    )

    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": REFINE_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    revised = "".join(
        b.text for b in response.content if b.type == "text"
    ).strip()
    # The agent sees both the fresh header_block and the previous letter's
    # (possibly stale) header, and tends to preserve the old one. The header
    # belongs to the profile — we own it deterministically. Strip whatever
    # the agent put on top and substitute the current contact_header().
    return _replace_header(revised, user.contact_header())


def _replace_header(letter_text: str, fresh_header: str) -> str:
    """Swap the letter's first paragraph (the header) with `fresh_header`.

    The agent emits the contact header as paragraph 1, separated from
    the body by a blank line. If the output has no `\n\n` we treat the
    whole thing as body and prepend the fresh header — better than
    silently skipping the substitution.
    """
    parts = letter_text.split("\n\n", 1)
    body = parts[1] if len(parts) == 2 else letter_text
    return f"{fresh_header.strip()}\n\n{body.lstrip()}"
