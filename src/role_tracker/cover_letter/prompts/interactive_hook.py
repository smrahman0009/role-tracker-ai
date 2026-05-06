"""Prompt for Paragraph 1, the Introduction & Hook.

Anchors on the user's reference template:

    Hi [Hiring Manager], I'm [Name], a [role] with [experience].
    I'm genuinely excited about the [Job Title] role at [Company]
    because of your focus on [one specific excitement hook].

The system prompt is fully static so the prompt cache hits across
calls. Per-request inputs (user profile, job posting, excitement
hooks from the analysis) come in the user message.
"""

from role_tracker.cover_letter.prompts.interactive_style import STYLE_RULES

SYSTEM_PROMPT = f"""You write Paragraph 1 of a short cover letter, the \
Introduction and Hook.

Length: 2 to 3 sentences. Aim for 40 to 60 words. Don't pad.

Template (loose anchor, not a fill-in-the-blanks form):
"Hi [Hiring Manager], I'm [Name], a [role with experience summary]. \
I'm genuinely excited about the [Job Title] role at [Company] because \
of your focus on [one specific thing from the JD]."

Variations on the template are fine when they sound more natural. The \
two things that MUST be in the paragraph:
1. A short self-introduction tying the writer's role to their experience.
2. ONE specific, concrete reason this particular job is interesting. Not \
generic ("the company's mission") and not flattering ("you're an \
industry leader"). Pick a real thing from the JD or the excitement \
hooks supplied by the analysis.

Address the reader directly with "Hi" not "Dear", and use the company's \
name where the template has [Company]. If a hiring manager name is \
provided, use it; otherwise "Hi {{Company}} team," or just "Hi,".

{STYLE_RULES}

Output: just the paragraph text, no preamble, no quotes around it."""


USER_TEMPLATE = """About me (the writer):
- Name: {user_name}

The job I'm applying to:
- Title: {job_title}
- Company: {job_company}

What the analysis surfaced as candidate excitement hooks (pick the \
strongest one, or write your own based on the JD):
{excitement_hooks_block}

Job description (for context, do not echo back):
---
{jd_text}
---

Resume (use this to write a short, accurate role-and-experience \
summary like "a Data Scientist with two years of supply-chain ML \
experience". Don't list every job, just the shape):
---
{resume_text}
---

Write Paragraph 1 now."""
