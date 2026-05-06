"""Interactive cover-letter generation, backend functions.

Three pure functions, one per stage of the user-in-the-loop flow:

    analyze(resume_text, jd_text)             -> MatchAnalysis
    draft(resume, jd, analysis, ...)          -> str           (Phase 2)
    finalize(hook, fit, close)                -> str           (Phase 6)

Pure in the sense that they take their dependencies (the Anthropic
client) as arguments rather than constructing one. That makes them
trivial to test against a stub.

Phase 1 ships only `analyze`.
"""

from __future__ import annotations

import json
from typing import Protocol

from anthropic import Anthropic
from pydantic import BaseModel, Field, ValidationError

from role_tracker.cover_letter.prompts import (
    interactive_close,
    interactive_fit,
    interactive_hook,
)
from role_tracker.cover_letter.prompts.interactive_analysis import (
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)

# Use a small model for analysis and individual paragraphs. Structured
# output with tight constraints is its sweet spot.
_ANALYSIS_MODEL = "claude-haiku-4-5"
_DRAFT_MODEL = "claude-haiku-4-5"
_MAX_TOKENS = 1024
_DRAFT_MAX_TOKENS = 512  # paragraphs are short


class MatchAnalysis(BaseModel):
    """Output of `analyze()`: the four lists that drive Phases 2-6."""

    strong: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    partial: list[str] = Field(default_factory=list)
    excitement_hooks: list[str] = Field(default_factory=list)


class AnalysisError(Exception):
    """Raised when the model returns text that isn't valid JSON in the
    expected schema. Callers can decide whether to retry or surface."""


# Minimal duck-typed Protocol so unit tests can pass a stub instead of
# a real Anthropic client.
class _AnthropicClientLike(Protocol):
    @property
    def messages(self) -> object: ...


PARAGRAPH_KEYS = ("hook", "fit", "close")


def analyze(
    resume_text: str,
    jd_text: str,
    *,
    client: Anthropic | _AnthropicClientLike,
    model: str = _ANALYSIS_MODEL,
) -> MatchAnalysis:
    """Run the match-analysis call and return a structured MatchAnalysis.

    Raises AnalysisError when the model's response cannot be parsed
    into the expected schema. Network/API errors propagate from the
    Anthropic client unchanged.
    """
    user_message = USER_TEMPLATE.format(
        resume_text=resume_text.strip(),
        jd_text=jd_text.strip(),
    )

    response = client.messages.create(  # type: ignore[union-attr]
        model=model,
        max_tokens=_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    text = _extract_text(response)
    return _parse_analysis(text)


# ----- internals -----------------------------------------------------------


def _extract_text(response: object) -> str:
    """Pull the text payload out of an Anthropic Messages response.

    Tolerates both real Anthropic responses (objects with .content list
    of TextBlocks) and dict-shaped stubs used in tests.
    """
    content = getattr(response, "content", None)
    if content is None and isinstance(response, dict):
        content = response.get("content")
    if not content:
        raise AnalysisError("empty response from model")

    parts: list[str] = []
    for block in content:
        # Real Anthropic blocks have .type and .text attributes.
        block_type = getattr(block, "type", None)
        text_attr = getattr(block, "text", None)
        if block_type is None and isinstance(block, dict):
            block_type = block.get("type")
            text_attr = block.get("text")
        if block_type == "text" and isinstance(text_attr, str):
            parts.append(text_attr)
    if not parts:
        raise AnalysisError("response had no text blocks")
    return "".join(parts).strip()


def _parse_analysis(text: str) -> MatchAnalysis:
    """Coerce the model's reply into a MatchAnalysis.

    Strips any code fences a misbehaving model might include despite
    instructions, then expects exactly one JSON object.
    """
    cleaned = text.strip()
    # Tolerate ```json ... ``` fences if the model produces them.
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -len("```")]
        cleaned = cleaned.strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AnalysisError(f"model did not return JSON: {exc}") from exc

    try:
        return MatchAnalysis.model_validate(payload)
    except ValidationError as exc:
        raise AnalysisError(f"JSON did not match schema: {exc}") from exc


# ============================================================================
# Phase 2: paragraph drafting
# ============================================================================


def _format_bullets(items: list[str]) -> str:
    """Render a list of bullet items for inclusion in a prompt."""
    if not items:
        return "(none)"
    return "\n".join(f"- {item}" for item in items)


def _build_hook_messages(
    *,
    user_name: str,
    job_title: str,
    job_company: str,
    excitement_hooks: list[str],
    jd_text: str,
    resume_text: str,
) -> tuple[str, list[dict]]:
    user_msg = interactive_hook.USER_TEMPLATE.format(
        user_name=user_name,
        job_title=job_title,
        job_company=job_company,
        excitement_hooks_block=_format_bullets(excitement_hooks),
        jd_text=jd_text.strip(),
        resume_text=resume_text.strip(),
    )
    return interactive_hook.SYSTEM_PROMPT, [
        {"role": "user", "content": user_msg}
    ]


def _build_fit_messages(
    *,
    user_name: str,
    job_title: str,
    job_company: str,
    analysis: MatchAnalysis,
    jd_text: str,
    resume_text: str,
) -> tuple[str, list[dict]]:
    user_msg = interactive_fit.USER_TEMPLATE.format(
        user_name=user_name,
        user_role_summary="",  # derived from resume in the prompt
        job_title=job_title,
        job_company=job_company,
        strong_block=_format_bullets(analysis.strong),
        gaps_block=_format_bullets(analysis.gaps),
        partial_block=_format_bullets(analysis.partial),
        jd_text=jd_text.strip(),
        resume_text=resume_text.strip(),
    )
    return interactive_fit.SYSTEM_PROMPT, [
        {"role": "user", "content": user_msg}
    ]


def _build_close_messages(
    *,
    user_name: str,
    user_first_name: str,
    job_title: str,
    job_company: str,
    resume_text: str,
) -> tuple[str, list[dict]]:
    user_msg = interactive_close.USER_TEMPLATE.format(
        user_name=user_name,
        user_first_name=user_first_name,
        user_role_summary="",
        job_title=job_title,
        job_company=job_company,
        resume_text=resume_text.strip(),
    )
    return interactive_close.SYSTEM_PROMPT, [
        {"role": "user", "content": user_msg}
    ]


def draft(
    *,
    paragraph: str,
    user_name: str,
    job_title: str,
    job_company: str,
    jd_text: str,
    resume_text: str,
    analysis: MatchAnalysis,
    committed: dict[str, str | None] | None = None,  # noqa: ARG001
    hint: str | None = None,                          # noqa: ARG001
    alternative_to: str | None = None,                # noqa: ARG001
    client: Anthropic | _AnthropicClientLike,
    model: str = _DRAFT_MODEL,
) -> str:
    """Generate one paragraph of a cover letter.

    `paragraph` selects the prompt: "hook", "fit", or "close".

    `committed`, `hint`, and `alternative_to` are accepted now to keep
    the function signature stable, but Phase 2 ignores them. Phases
    3 and 4 wire them in.
    """
    if paragraph not in PARAGRAPH_KEYS:
        raise ValueError(
            f"unknown paragraph {paragraph!r}, expected one of {PARAGRAPH_KEYS}"
        )

    user_first_name = (user_name.split() or [user_name])[0]

    if paragraph == "hook":
        system, messages = _build_hook_messages(
            user_name=user_name,
            job_title=job_title,
            job_company=job_company,
            excitement_hooks=analysis.excitement_hooks,
            jd_text=jd_text,
            resume_text=resume_text,
        )
    elif paragraph == "fit":
        system, messages = _build_fit_messages(
            user_name=user_name,
            job_title=job_title,
            job_company=job_company,
            analysis=analysis,
            jd_text=jd_text,
            resume_text=resume_text,
        )
    else:  # paragraph == "close"
        system, messages = _build_close_messages(
            user_name=user_name,
            user_first_name=user_first_name,
            job_title=job_title,
            job_company=job_company,
            resume_text=resume_text,
        )

    response = client.messages.create(  # type: ignore[union-attr]
        model=model,
        max_tokens=_DRAFT_MAX_TOKENS,
        system=system,
        messages=messages,
    )
    return _extract_text(response).strip()


def finalize(
    *,
    hook: str,
    fit: str,
    close: str,
) -> str:
    """Stitch the three committed paragraphs into a single letter.

    Phase 2 just joins them with blank lines. Phase 6 will wrap this
    with a Sonnet smoothing pass that enforces tone consistency
    across paragraphs and runs the style validator one last time.
    """
    parts = [p.strip() for p in (hook, fit, close) if p.strip()]
    return "\n\n".join(parts)
