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
from role_tracker.cover_letter.style_validator import clean, clean_list

# Concrete Anthropic model IDs. Aliased to "haiku" / "sonnet" at the
# API surface so the route accepts a stable enum even if Anthropic
# rolls out a new minor version.
HAIKU_MODEL = "claude-haiku-4-5"
SONNET_MODEL = "claude-sonnet-4-6"

# Defaults reflect what each task actually needs:
#   - Analysis is structured JSON → Haiku is genuinely as good, 5x cheaper.
#   - Summary and drafts are creative prose → Sonnet by default; the API
#     accepts an override so the user can A/B compare cheaply.
_ANALYSIS_MODEL = HAIKU_MODEL
_DRAFT_MODEL_DEFAULT = SONNET_MODEL
_SUMMARY_MODEL_DEFAULT = SONNET_MODEL

_MAX_TOKENS = 1024
_DRAFT_MAX_TOKENS = 512  # paragraphs are short
_SUMMARY_MAX_TOKENS = 384


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
    parsed = _parse_analysis(text)

    # Run every bullet through the style validator so em-dashes and
    # banned LLM tics don't leak through to the UI.
    return MatchAnalysis(
        strong=clean_list(parsed.strong),
        gaps=clean_list(parsed.gaps),
        partial=clean_list(parsed.partial),
        excitement_hooks=clean_list(parsed.excitement_hooks),
    )


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
        job_title=job_title,
        job_company=job_company,
        resume_text=resume_text.strip(),
    )
    return interactive_close.SYSTEM_PROMPT, [
        {"role": "user", "content": user_msg}
    ]


_DIFFERENT_ANGLE_PER_PARAGRAPH = {
    "hook": (
        "anchor on a different excitement hook from the analysis, or a "
        "different specific detail in the JD"
    ),
    "fit": (
        "lead with a different matched requirement and a different "
        "concrete piece of resume evidence (different project, "
        "employer, or artefact)"
    ),
    "close": (
        "pick a different through-line for the candidate's overall "
        "career shape; avoid the same opening framing as the previous "
        "version"
    ),
}


def _append_steering_to_user_message(
    messages: list[dict],
    paragraph: str,
    *,
    alternative_to: str | None = None,
    hint: str | None = None,
) -> list[dict]:
    """Append optional steering blocks to the user message.

    Two independent levers, either or both can be active:

    - `alternative_to`: the previous paragraph text the writer wants a
      meaningfully different version of. Triggers a per-paragraph axis
      instruction ("pick a different excitement hook", etc.) plus the
      previous version verbatim so the model can avoid repeating it.

    - `hint`: a one-line steering instruction from the writer ("lead
      with the Everstream supply-chain ML work, not LLM stuff"). The
      model is told to incorporate this for *this paragraph only*.

    Both blocks land at the END of the user message so the cached
    system prefix still hits across calls. When both are set, the hint
    appears first because it is the writer's stronger signal of what
    they want.
    """
    has_alt = bool(alternative_to and alternative_to.strip())
    has_hint = bool(hint and hint.strip())
    if not (has_alt or has_hint):
        return messages

    parts: list[str] = []

    if has_hint:
        parts.append(
            "\n\nSteering hint from the writer (apply to this paragraph "
            "and prioritise it over default choices, but stay within "
            f'the paragraph\'s rules above):\n"{hint.strip()}"'  # type: ignore[union-attr]
        )

    if has_alt:
        diff_axis = _DIFFERENT_ANGLE_PER_PARAGRAPH.get(
            paragraph,
            "produce something with a clearly different content shape, "
            "not a reworded version",
        )
        parts.append(
            "\n\nThe writer already saw this version of the paragraph "
            f"and wants a meaningfully different angle. Specifically: "
            f"{diff_axis}. Do NOT just reword the previous text. Pick "
            "a genuinely different anchor and write fresh prose around "
            f'it.\n\nPrevious version:\n"{alternative_to.strip()}"'  # type: ignore[union-attr]
        )

    addendum = "".join(parts)
    if messages and messages[0].get("role") == "user":
        messages[0]["content"] = messages[0]["content"] + addendum
    return messages


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
    hint: str | None = None,
    alternative_to: str | None = None,
    client: Anthropic | _AnthropicClientLike,
    model: str = _DRAFT_MODEL_DEFAULT,
) -> str:
    """Generate one paragraph of a cover letter.

    `paragraph` selects the prompt: "hook", "fit", or "close".

    `alternative_to` (Phase 3) triggers "different angle" mode: when
    set to the previous paragraph text, the prompt asks for a
    meaningfully different anchor (different excitement hook for Hook,
    different matched requirement / evidence for Fit, different
    through-line for Close).

    `hint` (Phase 4) is a one-line steering instruction from the
    writer that the model is told to prioritise for this paragraph
    only ("lead with the Everstream supply-chain ML work, not LLM
    stuff").

    Both can be active independently or together. Both land in the
    user message tail so the cached system prefix still hits.

    `committed` is accepted to keep the signature stable.
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

    messages = _append_steering_to_user_message(
        messages,
        paragraph,
        alternative_to=alternative_to,
        hint=hint,
    )

    response = client.messages.create(  # type: ignore[union-attr]
        model=model,
        max_tokens=_DRAFT_MAX_TOKENS,
        system=system,
        messages=messages,
    )
    return clean(_extract_text(response).strip())


def finalize(
    *,
    hook: str,
    fit: str,
    close: str,
) -> str:
    """Stitch the three committed paragraphs into a single letter.

    Phase 2 joined them with blank lines. Phase 5 adds a final
    style-validator pass over the joined output as belt-and-suspenders;
    individual paragraphs were already cleaned at draft() time, but the
    user may have edited them manually since, and a final sweep keeps
    the saved letter consistent. Phase 6 will wrap this with a Sonnet
    smoothing pass before the validator runs.
    """
    parts = [p.strip() for p in (hook, fit, close) if p.strip()]
    return clean("\n\n".join(parts))


# ============================================================================
# Phase 2.5 / 2.7: JD summary, three-section structured output
# ============================================================================


class JobSummary(BaseModel):
    """Three-section JD digest. Empty strings are permitted for any
    field the JD doesn't genuinely say anything about; the frontend
    skips empty sections rather than padding them."""

    role: str = ""
    requirements: str = ""
    context: str = ""


class SummaryError(Exception):
    """Raised when the model can't produce valid JSON in the expected
    schema. Mirrors AnalysisError's role for the analysis function."""


def summarize_job(
    jd_text: str,
    *,
    client: Anthropic | _AnthropicClientLike,
    model: str = _SUMMARY_MODEL_DEFAULT,
) -> JobSummary:
    """Three-section structured summary of a job description.

    Returns role / requirements / context strings. Each is 1-3
    sentences of prose; any field can be "" if the JD doesn't say
    anything genuine about it.

    Distinct from the match analysis: this is purely about the JOB,
    independent of the user's resume.

    Sonnet by default since this is creative prose where nuance and
    voice matter. Haiku is acceptable when the user explicitly asks
    to test it.

    Raises SummaryError when the model returns text that is not valid
    JSON or doesn't match the schema. Network errors propagate from
    the Anthropic client unchanged.
    """
    # Imported lazily to keep this module import-cheap when callers
    # don't use the summary feature.
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


def _parse_summary(text: str) -> JobSummary:
    """Coerce the model's reply into a JobSummary.

    Tolerates code fences the same way analysis parsing does.
    """
    cleaned = text.strip()
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
        raise SummaryError(f"model did not return JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SummaryError(f"expected a JSON object, got {type(payload).__name__}")

    try:
        return JobSummary.model_validate(payload)
    except ValidationError as exc:
        raise SummaryError(f"JSON did not match schema: {exc}") from exc
