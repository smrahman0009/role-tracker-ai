"""Prompt for Paragraph 3, the Close.

Anchors on the user's reference template:

    [user_self_summary_one_liner]. I'd love to connect and explore how
    I can contribute to your team. Thank you for your time and
    consideration.
    Best,
    [first_name]

The opening sentence summarises *who the writer is at a high level*,
not what they did at any one job. It tells the reader why this
candidate's whole shape is interesting, in one breath.
"""

from role_tracker.cover_letter.prompts.interactive_style import STYLE_RULES

SYSTEM_PROMPT = f"""You write Paragraph 3 of a short cover letter, the \
Close.

Length: 2 to 3 sentences plus the sign-off. Aim for 35 to 60 words \
total before the signature.

Template (loose anchor):
"[ONE sentence summarising the writer's overall shape, what makes \
their background interesting in one breath]. I'd love to connect and \
explore how I can contribute to your team. Thank you for your time \
and consideration.

Best,
[FirstName]"

The opening sentence is the only creative beat. It should be the \
writer's elevator pitch about themselves, not a recap of the previous \
paragraph. Examples of good shapes:
- "My hybrid background in data science and software engineering means \
I think about both modeling and production from day one."
- "I've spent the last three years turning research prototypes into \
shipped products, which is exactly the bridge this role asks for."
- "What I bring is a calibrated balance of speed and rigour, learned \
from running both ML experiments and customer-facing services."

The "I'd love to connect" sentence and the "Thank you" sentence are \
fine to keep close to the template. Don't over-engineer them.

The sign-off is "Best," on its own line, then the writer's first name \
on the next line.

{STYLE_RULES}

Output: the full paragraph plus the sign-off. No quotes, no extra \
preamble."""


USER_TEMPLATE = """About me (the writer):
- Name: {user_name}
- First name (for the sign-off): {user_first_name}
- Self-summary: {user_role_summary}

The job:
- Title: {job_title}
- Company: {job_company}

Resume (use this to write the elevator-pitch opener):
---
{resume_text}
---

Write Paragraph 3 plus sign-off now."""
