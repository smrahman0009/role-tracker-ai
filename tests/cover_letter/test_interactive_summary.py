"""Tests for cover_letter.interactive.summarize_job() + resolve_model()."""

import pytest

from role_tracker.cover_letter.interactive import (
    HAIKU_MODEL,
    SONNET_MODEL,
    resolve_model,
    summarize_job,
)


class _TextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)]


class _Messages:
    def __init__(self, text: str = "Five-sentence summary here.") -> None:
        self._text = text
        self.last_request: dict | None = None

    def create(self, **kwargs: object) -> _Response:
        self.last_request = kwargs
        return _Response(self._text)


class _StubClient:
    def __init__(self, text: str = "Five-sentence summary here.") -> None:
        self.messages = _Messages(text)


# ----- summarize_job ------------------------------------------------------


def test_summarize_returns_text() -> None:
    client = _StubClient("This is a senior data science role at Shopify.")
    text = summarize_job("JD body here.", client=client)
    assert text.startswith("This is")


def test_summarize_uses_sonnet_by_default() -> None:
    client = _StubClient()
    summarize_job("JD", client=client)
    assert client.messages.last_request["model"] == SONNET_MODEL


def test_summarize_honours_explicit_model() -> None:
    client = _StubClient()
    summarize_job("JD", client=client, model=HAIKU_MODEL)
    assert client.messages.last_request["model"] == HAIKU_MODEL


def test_summarize_strips_whitespace() -> None:
    client = _StubClient("\n\n  Summary text.  \n")
    text = summarize_job("JD", client=client)
    assert text == "Summary text."


def test_summarize_includes_jd_in_prompt() -> None:
    client = _StubClient()
    summarize_job("UNIQUE-JD-MARKER-12345", client=client)
    user_msg = client.messages.last_request["messages"][0]["content"]
    assert "UNIQUE-JD-MARKER-12345" in user_msg


# ----- resolve_model ------------------------------------------------------


def test_resolve_model_haiku_alias() -> None:
    assert resolve_model("haiku", default=SONNET_MODEL) == HAIKU_MODEL


def test_resolve_model_sonnet_alias() -> None:
    assert resolve_model("sonnet", default=HAIKU_MODEL) == SONNET_MODEL


def test_resolve_model_case_insensitive() -> None:
    assert resolve_model("SONNET", default=HAIKU_MODEL) == SONNET_MODEL
    assert resolve_model("Haiku", default=SONNET_MODEL) == HAIKU_MODEL


def test_resolve_model_none_uses_default() -> None:
    assert resolve_model(None, default=SONNET_MODEL) == SONNET_MODEL


def test_resolve_model_empty_string_uses_default() -> None:
    assert resolve_model("", default=HAIKU_MODEL) == HAIKU_MODEL


def test_resolve_model_passes_through_full_model_id() -> None:
    """Pinning a specific version should be allowed."""
    assert (
        resolve_model("claude-haiku-4-5", default=SONNET_MODEL)
        == "claude-haiku-4-5"
    )


def test_resolve_model_rejects_unknown_alias() -> None:
    with pytest.raises(ValueError):
        resolve_model("opus", default=SONNET_MODEL)
