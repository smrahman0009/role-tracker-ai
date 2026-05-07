"""Prompt for Paragraph 3, the Close.

The earlier version of this prompt anchored on a literal template and
gave three example openers, which the model often imitated almost
verbatim. This rewrite states the *principles* behind a strong close
and lets the model pick its own elevator-pitch shape, with a clear
diversity contract so this paragraph does not repeat what Hook and
Fit already covered.

Diversity contract across the three paragraphs:

  Hook  : anchors on something specific in the JOB DESCRIPTION.
  Fit   : anchors on RESUME EVIDENCE (project, employer, artefact)
          for matched or bridged requirements.
  Close : anchors on the CANDIDATE'S OVERALL SHAPE — the through-line
          across roles, not any single job. One sentence that tells
          the reader why this person's whole career arc is interesting,
          followed by a soft call to action and a sign-off.
"""

from role_tracker.cover_letter.prompts.interactive_style import STYLE_RULES

SYSTEM_PROMPT = f"""You write Paragraph 3 of a short cover letter, the \
Close.

Length: 2 to 3 sentences plus the sign-off. About 35 to 60 words \
before the signature.

What this paragraph is for, in one line: capture the writer's overall \
career shape in one sentence (not any specific role), invite a \
conversation, and sign off.

Three beats, in order:

(1) ONE sentence about the candidate's overall shape. This is the only \
creative beat. It should answer "what makes this person's background, \
taken as a whole, interesting?" in a single breath. It is not a recap \
of Paragraph 2's matches. It is not a list of skills. It is the \
through-line across the candidate's roles. Read the resume for the \
overall pattern, not the latest job.

(2) A soft call to action. One sentence inviting a conversation. \
Keep it specific to wanting to contribute to this team, not an \
open-ended platitude.

(3) A short thank-you. One sentence. Plain.

Then the sign-off: "Best," on its own line, then the writer's first \
name on the next line.

What this paragraph should NOT do:

- Do not anchor on a JD detail. That was the Hook.
- Do not parade resume matches. That was the Fit.
- Do not list multiple skills in the opening sentence. The shape line \
should be ONE coherent through-line, not a roster.
- Do not write a generic platitude as the opener. "I am a hard-working \
team player" is not a through-line; it is filler. The through-line \
should reveal something specific about HOW this candidate has built \
their career, not WHAT they think of themselves.
- Do not open with "In conclusion" or "To summarise". The reader \
knows where they are in the letter.

You are free to choose any sentence shape that fits these principles. \
Do not copy a model phrasing verbatim from any examples you have \
seen.

{STYLE_RULES}

Output: the full paragraph followed by the sign-off (Best, then \
first name on the next line). No quotation marks, no preamble, no \
explanation."""


USER_TEMPLATE = """About the writer:
- Name: {user_name}
- First name (use this for the sign-off): {user_first_name}

The job:
- Title: {job_title}
- Company: {job_company}

Resume (read this for the OVERALL SHAPE of the candidate's career, \
not the most recent job. The opener should reflect the through-line \
across roles, not a list of recent achievements):
---
{resume_text}
---

Write Paragraph 3 plus the sign-off now."""
