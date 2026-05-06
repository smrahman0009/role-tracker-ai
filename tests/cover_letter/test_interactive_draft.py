"""Tests for cover_letter.interactive.draft() and finalize()."""

import pytest

from role_tracker.cover_letter.interactive import (
    MatchAnalysis,
    draft,
    finalize,
)


class _TextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)]


class _Messages:
    def __init__(self, text: str = "Generated paragraph.") -> None:
        self._text = text
        self.last_request: dict | None = None

    def create(self, **kwargs: object) -> _Response:
        self.last_request = kwargs
        return _Response(self._text)


class _StubClient:
    def __init__(self, text: str = "Generated paragraph.") -> None:
        self.messages = _Messages(text)


def _analysis() -> MatchAnalysis:
    return MatchAnalysis(
        strong=["Python, 5 yrs (JD asks 3+)"],
        gaps=[],
        partial=["Distributed systems, 1 yr"],
        excitement_hooks=["their focus on real-time inference"],
    )


def _common_kwargs(client: _StubClient) -> dict:
    return dict(
        user_name="Shaikh Rahman",
        job_title="Senior Data Scientist",
        job_company="Shopify",
        jd_text="JD body here.",
        resume_text="Resume body here.",
        analysis=_analysis(),
        client=client,
    )


# ----- draft() shape & basic happy path -----------------------------------


def test_draft_hook_returns_text() -> None:
    client = _StubClient("Hi Shopify team, I'm Shaikh.")
    text = draft(paragraph="hook", **_common_kwargs(client))
    assert text == "Hi Shopify team, I'm Shaikh."


def test_draft_fit_returns_text() -> None:
    client = _StubClient("Your role requires Python and ML.")
    text = draft(paragraph="fit", **_common_kwargs(client))
    assert text.startswith("Your role")


def test_draft_close_returns_text() -> None:
    client = _StubClient("My background bridges DS and SWE.\n\nBest,\nShaikh")
    text = draft(paragraph="close", **_common_kwargs(client))
    assert "Best," in text


def test_draft_rejects_unknown_paragraph() -> None:
    client = _StubClient()
    with pytest.raises(ValueError):
        draft(paragraph="unknown", **_common_kwargs(client))


def test_draft_uses_haiku_model() -> None:
    client = _StubClient()
    draft(paragraph="hook", **_common_kwargs(client))
    assert client.messages.last_request["model"] == "claude-haiku-4-5"


# ----- prompt content checks ----------------------------------------------


def test_hook_prompt_includes_excitement_hooks() -> None:
    client = _StubClient()
    draft(paragraph="hook", **_common_kwargs(client))
    user_msg = client.messages.last_request["messages"][0]["content"]
    assert "their focus on real-time inference" in user_msg


def test_hook_prompt_includes_company_and_title() -> None:
    client = _StubClient()
    draft(paragraph="hook", **_common_kwargs(client))
    user_msg = client.messages.last_request["messages"][0]["content"]
    assert "Shopify" in user_msg
    assert "Senior Data Scientist" in user_msg


def test_fit_prompt_includes_strong_and_gaps_lists() -> None:
    client = _StubClient()
    analysis = MatchAnalysis(
        strong=["Python, 5 yrs"],
        gaps=["Kubernetes"],
        partial=["Docker, 2 yrs"],
        excitement_hooks=[],
    )
    draft(
        paragraph="fit",
        user_name="Shaikh Rahman",
        job_title="Senior DS",
        job_company="Shopify",
        jd_text="...",
        resume_text="...",
        analysis=analysis,
        client=client,
    )
    user_msg = client.messages.last_request["messages"][0]["content"]
    assert "Python, 5 yrs" in user_msg
    assert "Kubernetes" in user_msg
    assert "Docker, 2 yrs" in user_msg


def test_close_prompt_includes_first_name() -> None:
    """The close prompt expects a first name for the sign-off."""
    client = _StubClient()
    draft(paragraph="close", **_common_kwargs(client))
    user_msg = client.messages.last_request["messages"][0]["content"]
    # The first-name slot is "Shaikh" from "Shaikh Rahman"
    assert "Shaikh" in user_msg


def test_close_handles_single_word_name() -> None:
    """When the user has only one name, treat it as both full and first."""
    client = _StubClient()
    draft(
        paragraph="close",
        user_name="Mononym",
        job_title="DS",
        job_company="X",
        jd_text="...",
        resume_text="...",
        analysis=_analysis(),
        client=client,
    )
    user_msg = client.messages.last_request["messages"][0]["content"]
    assert "Mononym" in user_msg


# ----- whitespace / output normalization ----------------------------------


def test_draft_strips_whitespace() -> None:
    client = _StubClient("\n\n  paragraph with leading whitespace.  \n")
    text = draft(paragraph="hook", **_common_kwargs(client))
    assert text == "paragraph with leading whitespace."


# ----- finalize() ---------------------------------------------------------


def test_finalize_joins_with_blank_lines() -> None:
    text = finalize(
        hook="Hello there.",
        fit="I'm a great fit.",
        close="Cheers.",
    )
    assert text == "Hello there.\n\nI'm a great fit.\n\nCheers."


def test_finalize_strips_paragraph_whitespace() -> None:
    text = finalize(
        hook="  Hello.  \n",
        fit="\nFit here.\n",
        close="Close here.",
    )
    assert text == "Hello.\n\nFit here.\n\nClose here."


def test_finalize_skips_empty_paragraphs() -> None:
    """Empty inputs (e.g. user not yet committed close) get dropped.
    The route layer is responsible for refusing to call finalize when
    the letter is incomplete; here we just defend the contract."""
    text = finalize(hook="Hello.", fit="Fit.", close="")
    assert text == "Hello.\n\nFit."
