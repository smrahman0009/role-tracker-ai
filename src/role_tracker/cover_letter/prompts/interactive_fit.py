"""Prompt for Paragraph 2, Why You're a Fit.

Branches on the analysis. Strong-match path when there are no real
gaps; gap-honest path when there are. The branching happens inside the
prompt rather than in two separate prompts so the cached prefix stays
the same across both paths.

Template (loose anchor):

    [Strong match]
    Your role requires [req 1] and [req 2]. In my work at [employer],
    I built [specific example] that directly demonstrates [req 1].
    Additionally, I've shipped [relevant skill], which aligns with
    your need for [req 2].

    [Gap path]
    Your role requires [req 1] and [req 2]. I have strong experience
    with [req 1] from my work at [employer]. While my [req 2]
    experience is still developing, I'm actively building this skill
    through [growth evidence], and my foundation in
    [transferable skill] positions me to ramp up quickly.
"""

from role_tracker.cover_letter.prompts.interactive_style import STYLE_RULES

SYSTEM_PROMPT = f"""You write Paragraph 2 of a short cover letter, Why \
You're a Fit.

Length: 3 to 4 sentences. Aim for 60 to 100 words.

Inputs you'll receive: a Strong matches list, a Gaps list, and a \
Partial matches list, all derived from comparing the resume against \
the JD.

Two branches:

(A) STRONG MATCH BRANCH. Use when Gaps is empty or contains only \
cosmetic items the resume can plausibly absorb. Format:
"Your role requires [req 1] and [req 2]. In my work at [employer], I \
built [specific example] that directly demonstrates [req 1]. \
Additionally, I've shipped [relevant skill], which aligns with your \
need for [req 2]."

(B) GAP-HONEST BRANCH. Use when Gaps contains real items the resume \
does not cover. Format:
"Your role requires [req 1] and [req 2]. I have strong experience with \
[req 1] from my work at [employer]. While my [req 2] experience is \
still developing, I'm actively building this skill through [evidence], \
and my foundation in [transferable skill] positions me to ramp up \
quickly."

Pick the branch by reading the Gaps list. If it has 0 entries, use (A). \
If it has 1+ entry that genuinely matters for the role, use (B) on \
that gap. Partial matches help frame the bridge in branch (B); they \
become "my foundation in [transferable skill]" content.

Two requirements at most per paragraph. Even if the JD lists many \
requirements, pick the two most central. Pulling in three or four \
makes the paragraph too dense.

In branch (B), do NOT apologise or hedge excessively. "Still \
developing" is the strongest hedge allowed. Don't say "weak", "lacking", \
"unfortunately", or anything that primes the reader to doubt.

{STYLE_RULES}

Output: just the paragraph text, no preamble."""


USER_TEMPLATE = """About me (the writer):
- Name: {user_name}
- Self-summary: {user_role_summary}

The job:
- Title: {job_title}
- Company: {job_company}

Match analysis from earlier:

Strong matches:
{strong_block}

Gaps:
{gaps_block}

Partial matches:
{partial_block}

Job description (context only, do not echo):
---
{jd_text}
---

Resume (context only, do not echo):
---
{resume_text}
---

Write Paragraph 2 now. Choose the strong-match or gap-honest branch \
based on the Gaps list."""
