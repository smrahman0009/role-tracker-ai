"""Tests for cover_letter.interactive.summarize_job() + resolve_model()."""

import json

import pytest

from role_tracker.cover_letter.interactive import (
    HAIKU_MODEL,
    SONNET_MODEL,
    JobSummary,
    SummaryError,
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
    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.last_request: dict | None = None

    def create(self, **kwargs: object) -> _Response:
        self.last_request = kwargs
        if isinstance(self._payload, str):
            return _Response(self._payload)
        return _Response(json.dumps(self._payload))


class _StubClient:
    def __init__(self, payload: object | None = None) -> None:
        self.messages = _Messages(payload if payload is not None else _DEFAULT)


_DEFAULT = {
    "role": "Senior data scientist on Shopify's Risk team.",
    "requirements": "Python and 5+ years production ML.",
    "context": "Hybrid in Toronto. Suits ML practitioners shipping to prod.",
}


# ----- summarize_job ------------------------------------------------------


def test_summarize_returns_structured_model() -> None:
    client = _StubClient(_DEFAULT)
    result = summarize_job("JD body here.", client=client)
    assert isinstance(result, JobSummary)
    assert result.role.startswith("Senior data scientist")
    assert "Python" in result.requirements
    assert "Hybrid" in result.context


def test_summarize_uses_sonnet_by_default() -> None:
    client = _StubClient()
    summarize_job("JD", client=client)
    assert client.messages.last_request["model"] == SONNET_MODEL


def test_summarize_honours_explicit_model() -> None:
    client = _StubClient()
    summarize_job("JD", client=client, model=HAIKU_MODEL)
    assert client.messages.last_request["model"] == HAIKU_MODEL


def test_summarize_includes_jd_in_prompt() -> None:
    client = _StubClient()
    summarize_job("UNIQUE-JD-MARKER-12345", client=client)
    user_msg = client.messages.last_request["messages"][0]["content"]
    assert "UNIQUE-JD-MARKER-12345" in user_msg


def test_summarize_tolerates_code_fences() -> None:
    payload = json.dumps(_DEFAULT)
    fenced = f"```json\n{payload}\n```"
    client = _StubClient(fenced)
    result = summarize_job("JD", client=client)
    assert result.role.startswith("Senior")


def test_summarize_allows_empty_field() -> None:
    """If the JD doesn't say anything about, e.g., context, the model
    is allowed to return an empty string and we accept it."""
    payload = {
        "role": "Senior DS at Shopify.",
        "requirements": "Python and ML.",
        "context": "",
    }
    client = _StubClient(payload)
    result = summarize_job("JD", client=client)
    assert result.context == ""


def test_summarize_raises_on_non_json() -> None:
    client = _StubClient("here is some prose, not JSON")
    with pytest.raises(SummaryError):
        summarize_job("JD", client=client)


def test_summarize_raises_on_array_top_level() -> None:
    client = _StubClient(json.dumps([1, 2, 3]))
    with pytest.raises(SummaryError):
        summarize_job("JD", client=client)


def test_job_summary_defaults_to_empty_strings() -> None:
    """All three fields default to "" so callers don't have to
    handle missing keys."""
    s = JobSummary()
    assert s.role == ""
    assert s.requirements == ""
    assert s.context == ""


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
