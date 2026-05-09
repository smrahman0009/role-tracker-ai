"""Tests for the JD-highlights generator and the polish helper."""

from __future__ import annotations

from typing import Any

import pytest

from role_tracker.jobs.models import JobPosting
from role_tracker.screening.why_interested import (
    HighlightsError,
    _parse_highlights,
    generate_jd_highlights,
    polish_why_interested,
)

# ----- stubs -------------------------------------------------------------


class _TextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)]


class _Messages:
    def __init__(self, text: str) -> None:
        self._text = text
        self.last_call: dict | None = None

    def create(self, **kwargs: Any) -> _Response:
        self.last_call = kwargs
        return _Response(self._text)


class _StubAnthropic:
    def __init__(self, text: str) -> None:
        self.messages = _Messages(text)


def _job() -> JobPosting:
    return JobPosting(
        id="j1",
        title="Senior ML Engineer",
        company="Shopify",
        location="Toronto",
        description=(
            "Risk team. Production ML required. Hybrid two days/week. "
            "Salary $180-220k."
        ),
        url="https://example.com",
        posted_at="2026-04-28T00:00:00Z",
        source="jsearch",
        publisher="Shopify Careers",
    )


# ----- generate_jd_highlights -------------------------------------------


def test_generate_returns_parsed_highlights_list() -> None:
    client = _StubAnthropic(
        '{"highlights": ['
        '"Risk team builds fraud-detection ML",'
        '"Production ML required",'
        '"Hybrid two days/week"'
        "]}"
    )
    out = generate_jd_highlights(job=_job(), client=client)  # type: ignore[arg-type]
    assert out == [
        "Risk team builds fraud-detection ML",
        "Production ML required",
        "Hybrid two days/week",
    ]


def test_generate_does_not_send_resume() -> None:
    """The whole point of the rebrand: resume is NOT in the user message.
    The model only sees the JD."""
    client = _StubAnthropic('{"highlights": []}')
    generate_jd_highlights(job=_job(), client=client)  # type: ignore[arg-type]
    sent = client.messages.last_call
    assert sent is not None
    user_message = sent["messages"][0]["content"]
    assert "resume" not in user_message.lower()
    assert "<job_description>" in user_message


def test_generate_strips_empty_strings() -> None:
    client = _StubAnthropic(
        '{"highlights": ["valid one", "", "  ", "valid two"]}'
    )
    out = generate_jd_highlights(job=_job(), client=client)  # type: ignore[arg-type]
    assert out == ["valid one", "valid two"]


def test_generate_tolerates_code_fences() -> None:
    client = _StubAnthropic(
        '```json\n{"highlights": ["a", "b"]}\n```'
    )
    out = generate_jd_highlights(job=_job(), client=client)  # type: ignore[arg-type]
    assert out == ["a", "b"]


def test_generate_raises_on_non_json() -> None:
    client = _StubAnthropic("here are some highlights for you...")
    with pytest.raises(HighlightsError):
        generate_jd_highlights(job=_job(), client=client)  # type: ignore[arg-type]


def test_generate_raises_on_array_top_level() -> None:
    """Old (pre-rebrand) shape might return a bare array. Reject it."""
    client = _StubAnthropic('["a", "b"]')
    with pytest.raises(HighlightsError):
        generate_jd_highlights(job=_job(), client=client)  # type: ignore[arg-type]


def test_generate_raises_when_highlights_field_missing() -> None:
    client = _StubAnthropic('{"items": ["a", "b"]}')
    with pytest.raises(HighlightsError):
        generate_jd_highlights(job=_job(), client=client)  # type: ignore[arg-type]


def test_parse_highlights_directly_with_extra_whitespace() -> None:
    out = _parse_highlights('   {"highlights": ["one"]}   ')
    assert out == ["one"]


# ----- polish ------------------------------------------------------------


def test_polish_returns_text() -> None:
    client = _StubAnthropic("Polished version of the answer.")
    out = polish_why_interested(text="rough draft", client=client)  # type: ignore[arg-type]
    assert out == "Polished version of the answer."


def test_polish_sends_user_text_verbatim() -> None:
    client = _StubAnthropic("ok")
    polish_why_interested(text="my draft text", client=client)  # type: ignore[arg-type]
    assert client.messages.last_call is not None
    assert client.messages.last_call["messages"][0]["content"] == "my draft text"
