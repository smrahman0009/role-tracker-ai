"""Deterministic style cleanup for LLM-produced strings.

The interactive cover-letter prompts try hard to discourage em-dashes,
filler phrases, and the usual LLM tics. Prompting alone gets us to
roughly 80% compliance; the remaining 20% needs a regex sweep that
runs after every LLM call before the text reaches the user.

This module has one public function, `clean(text)`. It is pure: same
input always yields the same output, no LLM, no I/O. Safe to wrap
around any string before storing or returning.

Two passes:

  1. Em-dash and en-dash removal. Replaces typographic dashes with
     commas (the most common contextual substitute) so output never
     contains a "—" character.

  2. Phrase substitution. A short list of banned phrases gets either
     a clean replacement (for verbs like "leverage" → "use") or
     deletion (for filler like "Fundamentally,"). Replacements are
     case-insensitive but preserve the case of the original.

After both passes, whitespace and stray punctuation left by deletions
get tidied up.

The banned list is intentionally short. Aggressive editing would
sand off the writer's voice; this module's job is to remove the
patterns the LLM specifically over-uses, not to enforce a style
guide.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Banned-phrase substitutions.
#
# Order matters: longer phrases first so "delve into" matches before
# "delve" alone (if we ever add it). Each entry is (pattern, replacement);
# replacements can be empty strings for pure deletion.
#
# Replacements are deliberately neutral, not synonyms. "leverage" -> "use"
# is correct in nearly every context; "harness" -> "use" likewise. Where
# no clean substitution exists ("Fundamentally,"), we just delete.
# ---------------------------------------------------------------------------

_BANNED_PHRASES: list[tuple[str, str]] = [
    # Filler openers — always deletable, sentence reads cleaner without them.
    ("Fundamentally, ", ""),
    ("Ultimately, ", ""),
    ("At the end of the day, ", ""),
    ("It's worth noting that ", ""),
    ("It is worth noting that ", ""),
    ("I'd be remiss not to mention ", ""),
    ("I'd be remiss ", ""),

    # Stock metaphors LLMs love.
    ("navigate the landscape of ", "in "),
    ("navigate the landscape", "in this space"),
    ("in the realm of ", "in "),
    ("treasure trove of ", "rich source of "),
    ("treasure trove", "rich source"),
    ("a tapestry of ", "a mix of "),
    ("tapestry of ", "mix of "),

    # Filler verbs that read as marketing speak.
    ("delve into ", "explore "),
    ("delving into ", "exploring "),
    ("dive into ", "explore "),
    ("diving into ", "exploring "),
    ("leveraging ", "using "),
    ("leverage ", "use "),
    ("harnessing ", "using "),
    ("harness ", "use "),
    ("unlocking ", "enabling "),
    ("unlocks ", "enables "),
    ("unlock ", "enable "),

    # Buzzword adjectives.
    ("cutting-edge ", "modern "),
    ("state-of-the-art ", "modern "),
    ("best-in-class ", "strong "),
]

_BANNED_PATTERNS = [
    (re.compile(re.escape(phrase), re.IGNORECASE), replacement)
    for phrase, replacement in _BANNED_PHRASES
]


def _strip_dashes(text: str) -> str:
    """Replace em-dashes (—) and en-dashes (–) with commas.

    Hyphens (-) are left alone since they're legitimate inside words
    ("five-year") and number ranges ("3-5 years").
    """
    # Spaced em / en dash → comma + space (the typical typographic use)
    text = text.replace(" — ", ", ")
    text = text.replace(" – ", ", ")
    # Bare em / en dash with no surrounding spaces → comma
    text = text.replace("—", ",")
    text = text.replace("–", ",")
    return text


def _replace_banned(text: str) -> str:
    """Apply each banned-phrase substitution, preserving case at the
    start of replaced spans.

    For example: "Leverage Python" → "Use Python" (capital L mapped to U).
    """

    def case_preserving_sub(match: re.Match[str], replacement: str) -> str:
        original = match.group(0)
        if not replacement:
            return ""
        if original and original[0].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement

    for pattern, replacement in _BANNED_PATTERNS:
        text = pattern.sub(
            lambda m, r=replacement: case_preserving_sub(m, r), text
        )
    return text


def _tidy_whitespace(text: str) -> str:
    """Collapse double spaces and stray punctuation left by deletions.

    Keeps newlines (paragraphs) and tabs intact; collapses only
    runs of regular spaces.
    """
    # Collapse runs of spaces (but NOT newlines) into one.
    text = re.sub(r"[ \t]{2,}", " ", text)
    # ", ," or ", ." left over from a deleted phrase between commas.
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r",\s*,+", ",", text)
    text = re.sub(r"\.\s*\.+", ".", text)
    # A leading punctuation mark on a line is bad.
    text = re.sub(r"(?m)^[ \t]*[,;:]\s*", "", text)
    # Trailing whitespace per line.
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()


def clean(text: str | None) -> str:
    """Run the deterministic style sweep on a single string.

    Empty / None input passes through unchanged. The function is pure
    and idempotent: clean(clean(x)) == clean(x).
    """
    if not text:
        return ""
    text = _strip_dashes(text)
    text = _replace_banned(text)
    text = _tidy_whitespace(text)
    return text


def clean_list(items: list[str]) -> list[str]:
    """Apply clean() to each item; drop items that become empty.

    Useful for the analysis bullet lists where an item that was 100%
    filler (rare) would otherwise become an empty string.
    """
    cleaned = [clean(item) for item in items]
    return [item for item in cleaned if item.strip()]
