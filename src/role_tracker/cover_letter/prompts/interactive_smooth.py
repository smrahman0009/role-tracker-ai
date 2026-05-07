"""Prompt for the final smoothing pass.

After the user has committed three paragraphs (Hook, Fit, Close),
the finalize endpoint runs ONE Sonnet pass to:

  1. Clean transitions between paragraphs so the letter reads as
     a single voice rather than three independently-drafted slabs.
  2. Enforce tone consistency. If Hook landed casual and Close
     landed formal, this pass picks one and aligns the others.
  3. Trim accidental redundancy — e.g., if Hook and Fit both
     mention the same project, the second mention can lean on the
     first.
  4. Catch any banned phrases or em-dashes the per-paragraph
     style validator missed (defensive — the validator already
     ran on each paragraph at draft time).

Critically: this pass does NOT add new content, change the
candidate's claims, or invent facts. It is a polish pass over
text the user has already approved. If the input has accurate
specifics ("5 years Python at Everstream"), the output keeps them
unchanged.

Sonnet because tone and transition work compound; Haiku is
sometimes too literal here.
"""

from role_tracker.cover_letter.prompts.interactive_style import STYLE_RULES

SYSTEM_PROMPT = f"""You smooth a 3-paragraph cover letter into a \
final, ready-to-send version.

You will receive three paragraphs the writer has already approved: \
Hook (introduction), Fit (why the candidate fits), and Close \
(sign-off). They were drafted independently and may have rough seams.

Your job, in order:

1. Adjust transitions between paragraphs so the letter reads as a \
single voice, not three slabs. This usually means a small word or \
phrase change at the START of paragraphs 2 and 3, not a rewrite.

2. Pick the tone of the strongest paragraph and align the others \
to it. If one paragraph is more casual or more formal than the \
other two, nudge it toward consistency.

3. Trim accidental repetition. If Hook mentions a specific project \
and Fit mentions the same project, the Fit reference can be \
shortened ("that project") so the reader does not see the same \
words twice.

4. Catch any em-dashes or LLM-tic phrases the per-paragraph \
validator missed. (Em-dashes will be replaced with commas by a \
deterministic post-processor after you, so do not use them.)

Rules:

- DO NOT add new content. No new claims, no new projects, no new \
qualifications, no new excitement reasons. Every fact in the input \
must appear (or be paraphrased) in the output.
- DO NOT remove substantive content. If a paragraph names a real \
project, an employer, or a quantified result, keep it. You may \
shorten redundant mentions, never delete unique ones.
- DO NOT invent specifics that were not in the input. If the writer \
did not specify a year, a number, or a project name, do not add one.
- DO NOT restructure the letter into more or fewer paragraphs. \
Three paragraphs in, three paragraphs out, plus the sign-off.
- KEEP the sign-off ("Best,\\n[FirstName]") exactly as the input \
has it.

{STYLE_RULES}

Output: just the smoothed letter, three paragraphs separated by \
single blank lines, followed by the sign-off. No quotation marks \
around it, no preamble, no explanation."""


USER_TEMPLATE = """The three approved paragraphs, joined by blank \
lines as the writer left them:

---
{stitched_letter}
---

Smooth and return the final letter now. Three paragraphs plus \
sign-off, in the same order, without adding or removing content."""
