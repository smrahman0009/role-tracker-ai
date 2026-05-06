"""Shared style block injected into every paragraph-generation prompt.

Living in one place so when the user asks us to ban another phrase or
tweak the tone, we change it once. The rules here mirror the
deterministic style validator that runs after the LLM call (Phase 5)
so the model's output is *probably* clean and the validator
catches the rest.
"""

STYLE_RULES = """\
Style rules (these are non-negotiable):
- Plain text. No Markdown, no headings, no bullet points, no numbered lists.
- No em-dashes anywhere. Use commas or periods. (Yes, even em-dashes \
between clauses.)
- No filler phrases: "delve", "dive into", "navigate the landscape", \
"it's worth noting", "I'd be remiss", "leverage" as a verb, "harness", \
"unlock", "in the realm of", "Fundamentally,", "Ultimately,".
- Specific over abstract. Mention a real project, tool, or number from \
the resume. Avoid vague claims like "strong communicator" or "passionate".
- Honest over enthusiastic. The hiring manager has read 200 letters \
this week. They notice when claims are inflated.
- Match the length the section is supposed to be. Don't pad to look \
substantial. Padding reads as inexperience.
- Keep sentences under about 25 words. Shorter is usually better.
- Sound like a person, not a template."""
