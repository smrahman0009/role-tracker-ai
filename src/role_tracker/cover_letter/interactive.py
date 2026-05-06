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

from role_tracker.cover_letter.prompts.interactive_analysis import (
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)

# Use a small model for analysis — structured output with clear
# instructions is its sweet spot.
_ANALYSIS_MODEL = "claude-haiku-4-5"
_MAX_TOKENS = 1024


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
