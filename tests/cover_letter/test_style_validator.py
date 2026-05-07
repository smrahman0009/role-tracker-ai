"""Tests for cover_letter.style_validator.clean()."""

import pytest

from role_tracker.cover_letter.style_validator import clean, clean_list


# ----- em-dash + en-dash handling -----------------------------------------


@pytest.mark.parametrize(
    "input_text, expected",
    [
        # Spaced em-dash → comma
        ("I built ML systems — and shipped them.", "I built ML systems, and shipped them."),
        # Bare em-dash → comma
        ("Senior Data Scientist—Toronto", "Senior Data Scientist,Toronto"),
        # Spaced en-dash → comma
        ("Python – primary language", "Python, primary language"),
        # Bare en-dash → comma
        ("Python–primary", "Python,primary"),
        # Multiple em-dashes
        ("A — B — C", "A, B, C"),
    ],
)
def test_clean_strips_em_and_en_dashes(input_text: str, expected: str) -> None:
    assert clean(input_text) == expected


def test_clean_leaves_hyphens_alone() -> None:
    """Hyphens (-) are legitimate inside words and number ranges."""
    text = "5-7 years experience with state-of-the-art tools"
    # state-of-the-art is banned but the hyphen itself isn't the issue
    cleaned = clean(text)
    assert "5-7 years" in cleaned  # number range survives
    assert "state-of-the-art" not in cleaned  # banned phrase removed
    assert "modern" in cleaned  # replacement landed


# ----- banned phrase substitution -----------------------------------------


@pytest.mark.parametrize(
    "phrase, replacement",
    [
        ("delve into", "explore"),
        ("dive into", "explore"),
        ("leverage", "use"),
        ("leveraging", "using"),
        ("harness", "use"),
        ("unlock", "enable"),
        ("unlocking", "enabling"),
    ],
)
def test_clean_substitutes_banned_verb(
    phrase: str, replacement: str
) -> None:
    """Verbs that have clean replacements get substituted."""
    text = f"We {phrase} the data."
    cleaned = clean(text)
    assert replacement in cleaned
    assert phrase not in cleaned.lower()


@pytest.mark.parametrize(
    "phrase",
    [
        "Fundamentally,",
        "Ultimately,",
        "At the end of the day,",
        "It's worth noting that",
        "I'd be remiss",
    ],
)
def test_clean_deletes_filler_openers(phrase: str) -> None:
    text = f"{phrase} the system works."
    cleaned = clean(text)
    assert phrase.lower() not in cleaned.lower()
    # Sentence should still read cleanly.
    assert "the system works" in cleaned.lower()


def test_clean_substitutes_buzzword_adjectives() -> None:
    text = "Built with cutting-edge ML and state-of-the-art infra."
    cleaned = clean(text)
    assert "cutting-edge" not in cleaned
    assert "state-of-the-art" not in cleaned
    # Both replaced with the same neutral word.
    assert cleaned.count("modern") == 2


def test_clean_substitutes_landscape_metaphor() -> None:
    cleaned = clean("Navigate the landscape of LLM agents.")
    assert "navigate the landscape" not in cleaned.lower()
    assert "in" in cleaned.lower()


def test_clean_substitutes_treasure_trove() -> None:
    cleaned = clean("This dataset is a treasure trove of insights.")
    assert "treasure trove" not in cleaned.lower()
    assert "rich source" in cleaned.lower()


# ----- case preservation --------------------------------------------------


def test_clean_preserves_capital_at_sentence_start() -> None:
    """When a banned word is at the start of a sentence, the
    replacement should preserve the capital letter."""
    cleaned = clean("Leverage Python for data work.")
    assert cleaned.startswith("Use Python")


def test_clean_preserves_lowercase_mid_sentence() -> None:
    cleaned = clean("I will leverage Python for data work.")
    assert "use Python" in cleaned
    assert "Use Python" not in cleaned


def test_clean_handles_mixed_case_match() -> None:
    """LEVERAGE in caps should still match and substitute (preserving
    the leading capital)."""
    cleaned = clean("LEVERAGE existing tools.")
    assert "Use existing tools" in cleaned


# ----- whitespace tidy-up -------------------------------------------------


def test_clean_collapses_double_spaces_after_deletion() -> None:
    """When a filler phrase is deleted, the remaining sentence should
    not have double spaces."""
    cleaned = clean("Fundamentally, the system works well.")
    assert "  " not in cleaned
    assert cleaned == "the system works well."


def test_clean_strips_trailing_whitespace_per_line() -> None:
    cleaned = clean("Line one trailing spaces   \nLine two")
    assert cleaned == "Line one trailing spaces\nLine two"


def test_clean_preserves_paragraph_breaks() -> None:
    """Newlines should survive cleanly."""
    text = "First paragraph.\n\nSecond paragraph."
    cleaned = clean(text)
    assert "\n\n" in cleaned


# ----- edge cases ---------------------------------------------------------


def test_clean_empty_string() -> None:
    assert clean("") == ""


def test_clean_none() -> None:
    assert clean(None) == ""


def test_clean_string_without_issues() -> None:
    """A perfectly clean string should pass through unchanged."""
    text = "Built ML systems with Python at Everstream Analytics."
    assert clean(text) == text


def test_clean_is_idempotent() -> None:
    """Running clean twice should give the same result as once."""
    text = "We leverage cutting-edge tools — and that matters."
    once = clean(text)
    twice = clean(once)
    assert once == twice


# ----- clean_list helper --------------------------------------------------


def test_clean_list_drops_empty_items() -> None:
    """Items that become empty after cleaning (rare but possible)
    should be filtered out."""
    items = [
        "Built ML systems",
        "Fundamentally, ",  # becomes empty after deleting filler
        "5+ years Python",
    ]
    result = clean_list(items)
    assert result == ["Built ML systems", "5+ years Python"]


def test_clean_list_applies_substitutions_to_each() -> None:
    items = [
        "Leverage Python",
        "Harness ML pipelines",
        "Unlock business value",
    ]
    result = clean_list(items)
    assert all("Use" in item or "Enable" in item for item in result)
