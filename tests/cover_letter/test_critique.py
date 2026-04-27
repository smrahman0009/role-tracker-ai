"""Tests for the Haiku-based critique — mocked Anthropic client."""

import json
from unittest.mock import MagicMock

import pytest

from role_tracker.cover_letter.critique import (
    _extract_json,
    format_for_agent,
    run_critique,
)
from role_tracker.jobs.models import JobPosting


@pytest.fixture
def sample_job() -> JobPosting:
    return JobPosting(
        id="abc",
        title="ML Engineer",
        company="Shopify",
        location="Toronto",
        description="Build recommenders.",
        url="https://x.com",
        posted_at="2026-04-22T00:00:00Z",
        source="jsearch",
        publisher="Shopify",
    )


def _mock_client(returned_text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = returned_text
    response = MagicMock()
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


def test_extract_json_handles_clean_json() -> None:
    text = '{"verdict": "approved", "total": 92}'
    assert _extract_json(text) == {"verdict": "approved", "total": 92}


def test_extract_json_handles_wrapping_text() -> None:
    text = 'Here is the result:\n\n{"verdict": "approved", "total": 90}\n\nDone.'
    result = _extract_json(text)
    assert result["verdict"] == "approved"


def test_extract_json_returns_none_on_garbage() -> None:
    assert _extract_json("totally broken not json at all") is None


def test_run_critique_returns_parsed_result(sample_job: JobPosting) -> None:
    rubric_output = {
        "scores": {
            "hallucination": {"score": 25, "threshold_met": True},
            "tailoring": {"score": 18, "threshold_met": True},
        },
        "total": 88,
        "verdict": "approved",
        "priority_fixes": [],
        "notes": "Strong letter.",
    }
    client = _mock_client(json.dumps(rubric_output))
    result = run_critique(
        draft="Hello,\n\nBody.\n\nBest,\nName",
        resume_text="Resume.",
        job=sample_job,
        client=client,
    )
    assert result["verdict"] == "approved"
    assert result["total"] == 88


def test_run_critique_falls_back_on_bad_json(sample_job: JobPosting) -> None:
    client = _mock_client("I cannot produce JSON today, sorry.")
    result = run_critique(
        draft="draft",
        resume_text="resume",
        job=sample_job,
        client=client,
    )
    # Fallback always returns a valid structure.
    assert result["verdict"] == "minor_revision"
    assert len(result["priority_fixes"]) >= 1


def test_format_for_agent_shows_verdict_and_fixes() -> None:
    result = {
        "total": 78,
        "verdict": "minor_revision",
        "priority_fixes": ["Paragraph 2 lacks a bridge.", "Remove 'leverage'."],
        "scores": {
            "banned_phrases": {"score": 11, "threshold_met": False},
        },
        "notes": "Close, but needs tightening.",
    }
    out = format_for_agent(result)
    assert "78/110" in out
    assert "minor_revision" in out
    assert "banned_phrases" in out
    assert "leverage" in out
    assert "Notes" in out
