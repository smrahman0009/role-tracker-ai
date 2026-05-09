"""JD summary + match analysis helpers.

The "card-flow" drafting code (draft / finalize / smooth_letter) was
removed in May 2026 when the GenerateLetterDialog replaced the
per-paragraph cards. What stays in this module:

- summarize_job: 3-section JD digest used by the JobSummaryPanel
- analyze: 4-list resume↔JD match analysis used by the
  CoverLetterAnalysisPanel (restored May 2026 after a misguided
  bundle-deletion)

Both are single Anthropic calls returning structured JSON.

Module name kept for now so existing imports resolve; rename to
`cover_letter/analysis.py` is a future cleanup.
"""

from __future__ import annotations

import json
from typing import Protocol

from anthropic import Anthropic
from pydantic import BaseModel, Field, ValidationError

from role_tracker.cover_letter.style_validator import clean, clean_list

# Concrete Anthropic model IDs. Aliased to "haiku" / "sonnet" at the
# API surface so the route accepts a stable enum even if Anthropic
# rolls out a new minor version.
HAIKU_MODEL = "claude-haiku-4-5"
SONNET_MODEL = "claude-sonnet-4-6"

# Sonnet by default — JD digests benefit from nuance. Haiku stays
# selectable so the user can A/B compare cheaply.
_SUMMARY_MODEL_DEFAULT = SONNET_MODEL
_SUMMARY_MAX_TOKENS = 384

# Match analysis defaults to Sonnet too. Haiku produces valid JSON
# but Sonnet is meaningfully better at picking what's *worth* flagging
# vs what's just keyword-shaped overlap. The toggle on the panel lets
# the user downgrade to Haiku for the cheaper run.
_ANALYSIS_MODEL_DEFAULT = SONNET_MODEL
_ANALYSIS_MAX_TOKENS = 1024


def resolve_model(choice: str | None, *, default: str) -> str:
    """Translate an API-level "haiku"/"sonnet" alias to a real model ID.

    `None` and empty string fall through to the supplied default.
    Raises ValueError on an unknown alias so route validation surfaces
    a 422 instead of a silent 500.
    """
    if not choice:
        return default
    lowered = choice.lower()
    if lowered == "haiku":
        return HAIKU_MODEL
    if lowered == "sonnet":
        return SONNET_MODEL
    # Allow callers to pass a fully-qualified model ID through if they
    # want to pin a specific version.
    if lowered.startswith("claude-"):
        return choice
    raise ValueError(
        f"unknown model choice {choice!r}; expected 'haiku' or 'sonnet'"
    )


class _AnthropicClientLike(Protocol):
    @property
    def messages(self) -> object: ...


# ----- JD summary --------------------------------------------------------


class JobSummary(BaseModel):
    """Three-section JD digest. Empty strings are permitted for any
    field the JD doesn't genuinely say anything about; the frontend
    skips empty sections rather than padding them."""

    role: str = ""
    requirements: str = ""
    context: str = ""


class SummaryError(Exception):
    """Raised when the model can't produce valid JSON in the expected
    schema."""


def summarize_job(
    jd_text: str,
    *,
    client: Anthropic | _AnthropicClientLike,
    model: str = _SUMMARY_MODEL_DEFAULT,
) -> JobSummary:
    """Three-section structured summary of a job description.

    Sonnet by default since this is creative prose where nuance and
    voice matter. Haiku is acceptable when the user explicitly asks
    to test it.

    Raises SummaryError when the model returns text that is not valid
    JSON or doesn't match the schema. Network errors propagate from
    the Anthropic client unchanged.
    """
    # Imported lazily so this module stays import-cheap when callers
    # only use resolve_model().
    from role_tracker.cover_letter.prompts import job_summary

    response = client.messages.create(  # type: ignore[union-attr]
        model=model,
        max_tokens=_SUMMARY_MAX_TOKENS,
        system=job_summary.SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": job_summary.USER_TEMPLATE.format(
                    jd_text=jd_text.strip()
                ),
            }
        ],
    )
    text = _extract_text(response).strip()
    parsed = _parse_summary(text)

    # Run each section through the style validator so em-dashes and
    # banned LLM tics don't leak through to the UI.
    return JobSummary(
        role=clean(parsed.role),
        requirements=clean(parsed.requirements),
        context=clean(parsed.context),
    )


# ----- internals --------------------------------------------------------


def _extract_text(response: object) -> str:
    """Pull the text payload out of an Anthropic Messages response.

    Tolerates both real Anthropic responses (objects with .content list
    of TextBlocks) and dict-shaped stubs used in tests.
    """
    content = getattr(response, "content", None)
    if content is None and isinstance(response, dict):
        content = response.get("content")
    if not content:
        raise SummaryError("empty response from model")

    parts: list[str] = []
    for block in content:
        block_type = getattr(block, "type", None)
        text_attr = getattr(block, "text", None)
        if block_type is None and isinstance(block, dict):
            block_type = block.get("type")
            text_attr = block.get("text")
        if block_type == "text" and isinstance(text_attr, str):
            parts.append(text_attr)
    if not parts:
        raise SummaryError("response had no text blocks")
    return "".join(parts).strip()


def _parse_summary(text: str) -> JobSummary:
    """Coerce the model's reply into a JobSummary.

    Tolerates ```json fences the model sometimes wraps the response in.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -len("```")]
        cleaned = cleaned.strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SummaryError(f"model did not return JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SummaryError(f"expected a JSON object, got {type(payload).__name__}")

    try:
        return JobSummary.model_validate(payload)
    except ValidationError as exc:
        raise SummaryError(f"JSON did not match schema: {exc}") from exc


# ----- Match analysis ----------------------------------------------------


class MatchAnalysis(BaseModel):
    """Output of `analyze()`: four lists comparing resume to JD.

    Drives the CoverLetterAnalysisPanel on the job detail page. The
    user reads them as input to the Generate dialog ("address the
    distributed-systems gap"); the agent doesn't read them directly.
    """

    strong: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    partial: list[str] = Field(default_factory=list)
    excitement_hooks: list[str] = Field(default_factory=list)


class AnalysisError(Exception):
    """Raised when the model returns text that isn't valid JSON in the
    expected schema. Routes translate to HTTP 502."""


def analyze(
    resume_text: str,
    jd_text: str,
    *,
    client: Anthropic | _AnthropicClientLike,
    model: str = _ANALYSIS_MODEL_DEFAULT,
) -> MatchAnalysis:
    """Run the match-analysis call and return a structured MatchAnalysis.

    Default model is Sonnet — better judgment than Haiku at picking
    what's distinctive about the resume↔JD overlap (vs surface keyword
    matches). The route layer accepts a model alias so the user can
    flip to Haiku for the cheaper run via the panel's model toggle.

    Raises AnalysisError when the model's response can't be parsed.
    Network/API errors propagate from the Anthropic client unchanged.
    """
    # Imported lazily so the module stays import-cheap when callers
    # only use summarize_job.
    from role_tracker.cover_letter.prompts.interactive_analysis import (
        SYSTEM_PROMPT,
        USER_TEMPLATE,
    )

    user_message = USER_TEMPLATE.format(
        resume_text=resume_text.strip(),
        jd_text=jd_text.strip(),
    )

    response = client.messages.create(  # type: ignore[union-attr]
        model=model,
        max_tokens=_ANALYSIS_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    text = _extract_text_for_analysis(response)
    parsed = _parse_analysis(text)

    # Run every bullet through the style validator so em-dashes and
    # banned LLM tics don't leak through to the UI.
    return MatchAnalysis(
        strong=clean_list(parsed.strong),
        gaps=clean_list(parsed.gaps),
        partial=clean_list(parsed.partial),
        excitement_hooks=clean_list(parsed.excitement_hooks),
    )


def _extract_text_for_analysis(response: object) -> str:
    """Same shape as _extract_text but raises AnalysisError instead of
    SummaryError so the route can translate to the right HTTP code."""
    content = getattr(response, "content", None)
    if content is None and isinstance(response, dict):
        content = response.get("content")
    if not content:
        raise AnalysisError("empty response from model")

    parts: list[str] = []
    for block in content:
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
    """Coerce the model's reply into a MatchAnalysis. Tolerates code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
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
