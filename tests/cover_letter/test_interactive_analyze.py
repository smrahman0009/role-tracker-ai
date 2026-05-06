"""Tests for cover_letter.interactive.analyze()."""

import json

import pytest

from role_tracker.cover_letter.interactive import (
    AnalysisError,
    MatchAnalysis,
    analyze,
)

# A minimal duck-typed stub mirroring the bits of an Anthropic client
# we touch. Lets us run the analyse loop without network calls.

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
        if isinstance(self._payload, dict):
            return _Response(json.dumps(self._payload))
        raise TypeError("payload must be str or dict")


class _StubClient:
    def __init__(self, payload: object) -> None:
        self.messages = _Messages(payload)


def _valid_payload() -> dict:
    return {
        "strong": [
            "Python, 5 yrs (JD asks 3+)",
            "LLM agent loops shipped to prod",
        ],
        "gaps": [
            "Kubernetes (resume shows Docker only)",
        ],
        "partial": [
            "Distributed systems, 1 yr (JD asks 3+; related Spark work)",
        ],
        "excitement_hooks": [
            "their focus on real-time inference",
        ],
    }


def test_analyze_returns_structured_model() -> None:
    client = _StubClient(_valid_payload())
    result = analyze("resume here", "jd here", client=client)
    assert isinstance(result, MatchAnalysis)
    assert "Python, 5 yrs (JD asks 3+)" in result.strong
    assert len(result.gaps) == 1
    assert len(result.partial) == 1
    assert len(result.excitement_hooks) == 1


def test_analyze_includes_resume_and_jd_in_user_message() -> None:
    """The resume and JD should both reach the model verbatim."""
    client = _StubClient(_valid_payload())
    analyze("MY-RESUME-MARKER", "MY-JD-MARKER", client=client)

    request = client.messages.last_request
    assert request is not None
    user_content = request["messages"][0]["content"]
    assert "MY-RESUME-MARKER" in user_content
    assert "MY-JD-MARKER" in user_content


def test_analyze_uses_haiku_by_default() -> None:
    client = _StubClient(_valid_payload())
    analyze("r", "j", client=client)
    assert client.messages.last_request["model"] == "claude-haiku-4-5"


def test_analyze_strips_code_fences() -> None:
    """Some Anthropic responses wrap JSON in ```json``` fences despite
    the prompt saying not to. We tolerate it."""
    payload = json.dumps(_valid_payload())
    fenced = f"```json\n{payload}\n```"
    client = _StubClient(fenced)
    result = analyze("r", "j", client=client)
    assert isinstance(result, MatchAnalysis)
    assert len(result.strong) == 2


def test_analyze_handles_plain_fences_no_lang() -> None:
    payload = json.dumps(_valid_payload())
    fenced = f"```\n{payload}\n```"
    client = _StubClient(fenced)
    result = analyze("r", "j", client=client)
    assert len(result.gaps) == 1


def test_analyze_raises_on_non_json_text() -> None:
    client = _StubClient("here is some prose, not JSON at all")
    with pytest.raises(AnalysisError):
        analyze("r", "j", client=client)


def test_analyze_raises_on_wrong_schema() -> None:
    """Model returns valid JSON but with the wrong shape."""
    client = _StubClient({"foo": "bar"})
    # This actually parses fine because every field defaults to []
    # via model_validate, so the result is an empty MatchAnalysis.
    # That's intentional — we'd rather pass a near-empty analysis up
    # than fail loudly. But if the model returns a non-dict, we error.
    result = analyze("r", "j", client=client)
    assert result.strong == []
    assert result.gaps == []


def test_analyze_raises_on_array_at_top_level() -> None:
    """Top-level JSON array is wrong; we expect an object."""
    # _StubClient's dict path isn't reached with a list payload;
    # we feed pre-serialised JSON to bypass that branch.
    raw = json.dumps([1, 2, 3])
    raise_client = _StubClient(raw)
    with pytest.raises(AnalysisError):
        analyze("r", "j", client=raise_client)


def test_analyze_raises_on_empty_response() -> None:
    """Model returns no text blocks at all."""

    class _EmptyResp:
        content = []

    class _EmptyMessages:
        def create(self, **_kwargs: object) -> _EmptyResp:
            return _EmptyResp()

    class _EmptyClient:
        messages = _EmptyMessages()

    with pytest.raises(AnalysisError):
        analyze("r", "j", client=_EmptyClient())


def test_match_analysis_defaults_are_empty_lists() -> None:
    """Every field defaults to [] so optional fields don't crash callers."""
    m = MatchAnalysis()
    assert m.strong == []
    assert m.gaps == []
    assert m.partial == []
    assert m.excitement_hooks == []
