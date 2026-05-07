"""Prompt for Paragraph 1, the Introduction & Hook.

The earlier version of this prompt was too literal a template ("Hi
[Hiring Manager], I'm [Name]..."), which made every Hook read the
same way regardless of writer or job. This rewrite states *principles*
instead of an exact form, and makes Hook responsible for one specific
beat the other paragraphs do not cover.

Diversity contract across the three paragraphs:

  Hook  : anchors on something specific in the JOB DESCRIPTION that
          resonates with the writer (the "why this role" angle).
  Fit   : anchors on RESUME EVIDENCE (specific project, employer,
          skill) for matched or partially matched requirements.
  Close : anchors on the CANDIDATE'S OVERALL SHAPE (career narrative
          across roles), independent of any single job.

Hook should not duplicate Fit's job (parading skill matches) or
Close's job (summarising the candidate's whole shape).
"""

from role_tracker.cover_letter.prompts.interactive_style import STYLE_RULES

SYSTEM_PROMPT = f"""You write Paragraph 1 of a short cover letter, the \
Introduction and Hook.

Length: 2 to 3 sentences. About 40 to 60 words. Don't pad.

What this paragraph is for, in one line: introduce the writer briefly \
and name ONE specific thing in the job description that genuinely \
makes this role interesting.

Things you must include:
1. A short self-introduction tying the writer's role and experience \
to the job they're applying for. Keep this concise; the resume covers \
the long version.
2. ONE specific, concrete reason this particular job is worth their \
attention. This must come from the JD or the analysis's excitement \
hooks. It should be something a real person could be excited about, \
not boilerplate.

Things you should NOT do:
- Do not list multiple reasons. One is stronger than three.
- Do not use generic excitement phrases like "I'm passionate about \
your mission" or "your company is a leader in the industry". A reader \
who has read 200 cover letters this week will skim past those.
- Do not parade skill matches in this paragraph. That is Paragraph 2's \
job. Keep this paragraph focused on the JOB, not the candidate's \
qualifications.
- Do not summarise the candidate's overall shape ("My background \
combines X and Y..."). That is Paragraph 3's job.
- Do not start with "I am writing to apply for..." or any variant. The \
recipient knows what document they're reading.

Greeting: address the reader directly. If a hiring manager name was \
provided, use it. Otherwise "Hi {{Company}} team," or simply "Hi,". \
Avoid "Dear" and "To Whom It May Concern".

You are free to choose any sentence shape that fits the principles \
above. The exact words "I'm genuinely excited about..." are NOT \
required. Write like a real person introducing themselves.

{STYLE_RULES}

Output: just the paragraph text. No preamble, no quotation marks \
around it, no explanation."""


USER_TEMPLATE = """About the writer:
- Name: {user_name}

The job they're applying to:
- Title: {job_title}
- Company: {job_company}

Candidate excitement hooks the analysis surfaced (pick the most \
specific one, or write your own based on the JD). Each is a real \
detail from the JD that this candidate, given their background, \
might genuinely care about:
{excitement_hooks_block}

Job description (use this if the excitement hooks above are weak; \
do not echo it back):
---
{jd_text}
---

Resume (use this only to derive a short, accurate role-and-experience \
summary for the self-introduction; do not parade skills here, that \
is Paragraph 2's job):
---
{resume_text}
---

Write Paragraph 1 now."""
