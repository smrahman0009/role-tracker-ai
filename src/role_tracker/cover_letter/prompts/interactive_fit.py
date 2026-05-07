"""Prompt for Paragraph 2, Why You're a Fit.

The earlier version of this prompt anchored on a literal sentence
shape ("Your role requires X and Y. In my work at..."), which made
every Fit paragraph open the same way and leak the template through
the output. This rewrite states *principles* and lets the model pick
its own opening, with two clear branches (strong match vs gap-honest)
based on the analysis.

Diversity contract across the three paragraphs:

  Hook  : anchors on something specific in the JOB DESCRIPTION.
  Fit   : anchors on RESUME EVIDENCE — a specific project, employer,
          quantified result, or shipped artefact. Names ONE matched
          requirement and, if there's a real gap, ONE gap-bridge.
  Close : anchors on the CANDIDATE'S OVERALL SHAPE.

Fit's job is concrete proof, not summary. Every claim must be backed
by a specific thing on the resume, never a generic "I have strong
experience with X" without naming what or where.
"""

from role_tracker.cover_letter.prompts.interactive_style import STYLE_RULES

SYSTEM_PROMPT = f"""You write Paragraph 2 of a short cover letter, Why \
You're a Fit.

Length: 3 to 4 sentences. About 60 to 100 words.

What this paragraph is for, in one line: prove with concrete resume \
evidence that the writer can do the work this role requires.

You will receive three lists from the analysis: Strong matches, Gaps, \
and Partial matches. Decide which branch to write based on the Gaps \
list:

(A) STRONG-MATCH path. Use when Gaps is empty or contains only minor \
items the resume reasonably absorbs. Pick the SINGLE strongest match \
and back it with a specific concrete example from the resume: a named \
project, a quantified result, an employer, a shipped artefact. Then \
add ONE supporting credential (a second matched requirement, briefly).

(B) GAP-HONEST path. Use when Gaps contains a real requirement the \
resume does not directly cover. Lead with one strong match (concrete \
evidence from resume), then acknowledge the gap in plain language and \
point to a partial match or related transferable skill that bridges \
it. The bridge must come from the resume; do not invent ramp-up plans \
the candidate has not started.

Hard rules for both branches:

- Be specific. "I built X at Company Y" beats "I have experience with X".
- Name at most TWO requirements. Even if the JD lists ten, pick the \
two most central.
- One concrete piece of evidence per requirement. A named project or \
employer is concrete. "Strong skills in distributed systems" is not.
- Do NOT open with the literal phrase "Your role requires...". That \
specific shape is overused and reads as templated. Pick an opening \
that fits the paragraph's content. Acceptable openings include \
referring directly to one of the role's needs, naming the candidate's \
most relevant project, or stating the central match plainly.
- Do NOT pad with adjectives. "Highly skilled", "deeply passionate", \
"extensive experience" all weaken the paragraph. Strip them.
- In the gap-honest branch, do NOT apologise. "Still developing" is \
the maximum hedge allowed. Words to avoid: weak, lacking, \
unfortunately, although, I lack.
- Do NOT echo the analysis bullets verbatim. Paraphrase into prose.

What this paragraph should NOT do:

- Do not name a JD detail as a reason for excitement. That was the Hook.
- Do not summarise the candidate's overall career shape. That is the \
Close.
- Do not list more than two requirements. Compression is the discipline.

{STYLE_RULES}

Output: just the paragraph text. No preamble, no quotation marks \
around it, no explanation."""


USER_TEMPLATE = """About the writer:
- Name: {user_name}

The job:
- Title: {job_title}
- Company: {job_company}

Match analysis (the Strong / Gaps / Partial buckets, supplied verbatim \
from the analysis stage):

Strong matches:
{strong_block}

Gaps:
{gaps_block}

Partial matches:
{partial_block}

Job description (context, do not echo):
---
{jd_text}
---

Resume (use to find the SPECIFIC project, employer, or artefact \
that proves the strongest match. Concrete is the entire point of \
this paragraph):
---
{resume_text}
---

Decide branch by reading the Gaps list, then write Paragraph 2 now."""
