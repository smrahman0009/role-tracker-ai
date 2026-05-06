"""System prompts for the interactive cover-letter flow.

Each prompt lives in its own module so the text is easy to find,
diff, and unit-test against fixed inputs. The prompts are kept as
constants rather than f-strings so prompt-cache prefixes line up
verbatim across calls.
"""
