"""Tests for the agentic cover-letter generator. Mocked Anthropic client."""

import json as _json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from role_tracker.cover_letter.agent import generate_cover_letter_agent
from role_tracker.jobs.models import JobPosting
from role_tracker.users.models import UserProfile


@pytest.fixture
def sample_user() -> UserProfile:
    return UserProfile(
        id="smrah",
        name="Shaikh Mushfikur Rahman",
        email="smrahman0009@gmail.com",
        phone="782-882-0852",
        city="Halifax, NS",
        resume_path=Path("data/resumes/smrah.pdf"),
        queries=[],
    )


@pytest.fixture
def sample_job() -> JobPosting:
    return JobPosting(
        id="abc",
        title="Staff ML Engineer",
        company="Shopify",
        location="Toronto",
        description="Build recommender systems.",
        url="https://shopify.com/careers/1",
        posted_at="2026-04-22T00:00:00Z",
        source="jsearch",
        publisher="Shopify Careers",
    )


@pytest.fixture
def sample_resume() -> str:
    return (
        "SUMMARY\nNLP engineer.\n\n"
        "EXPERIENCE\nEverstream — 92% accuracy NLP pipeline with transformers.\n\n"
        "EDUCATION\nDalhousie University."
    )


def _tool_use_block(tool_name: str, tool_input: dict, block_id: str = "id1"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = block_id
    return block


def _text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _response(content: list, stop_reason: str = "tool_use"):
    r = MagicMock()
    r.content = content
    r.stop_reason = stop_reason
    return r


def _ok_letter() -> str:
    """A letter that passes deterministic checks (300+ words, paras <130)."""
    p1 = " ".join(["word"] * 100)
    p2 = " ".join(["word"] * 120)
    p3 = " ".join(["word"] * 100)
    return f"Header\n\nHello,\n\n{p1}\n\n{p2}\n\n{p3}\n\nBest,\nX"


def test_agent_completes_on_save_letter(
    sample_user: UserProfile, sample_job: JobPosting, sample_resume: str
) -> None:
    # Full mandatory flow: read JD → read resume → strategy → critique → save.
    approved_json = _json.dumps(
        {"total": 100, "verdict": "approved", "priority_fixes": [], "scores": {}}
    )
    client = MagicMock()
    client.messages.create.side_effect = [
        _response([_tool_use_block("read_job_description", {}, "id1")]),
        _response(
            [_tool_use_block(
                "read_resume_section", {"topic": "transformers"}, "id2"
            )]
        ),
        _response(
            [_tool_use_block(
                "commit_to_strategy",
                {
                    "fit_assessment": "HIGH",
                    "fit_reasoning": "Direct match.",
                    "narrative_angle": "NLP work maps to ranking.",
                    "primary_project": "Company Name Resolution",
                },
                "id3",
            )]
        ),
        _response(
            [_tool_use_block(
                "critique_draft",
                {"draft": _ok_letter()},
                "id4",
            )]
        ),
        _response([_text_block(approved_json)], stop_reason="end_turn"),
        _response(
            [_tool_use_block("save_letter", {"text": _ok_letter()}, "id5")]
        ),
    ]

    letter = generate_cover_letter_agent(
        user=sample_user,
        resume_text=sample_resume,
        job=sample_job,
        client=client,
    )
    assert letter.startswith("Header")
    assert "Best" in letter


def test_agent_raises_on_no_save(
    sample_user: UserProfile, sample_job: JobPosting, sample_resume: str
) -> None:
    client = MagicMock()
    client.messages.create.return_value = _response(
        [_text_block("I'll think about it.")], stop_reason="end_turn"
    )

    with pytest.raises(RuntimeError, match="without saving"):
        generate_cover_letter_agent(
            user=sample_user,
            resume_text=sample_resume,
            job=sample_job,
            client=client,
            max_iterations=3,
        )


def test_agent_passes_tools_to_claude(
    sample_user: UserProfile, sample_job: JobPosting, sample_resume: str
) -> None:
    client = MagicMock()
    client.messages.create.side_effect = [
        _response(
            [_tool_use_block("save_letter", {"text": _ok_letter()}, "id1")]
        ),
    ]
    # Will fail (no strategy) but we only care about the tools passed.
    try:
        generate_cover_letter_agent(
            user=sample_user,
            resume_text=sample_resume,
            job=sample_job,
            client=client,
            max_iterations=1,
        )
    except RuntimeError:
        pass
    kwargs = client.messages.create.call_args.kwargs
    tool_names = {t["name"] for t in kwargs["tools"]}
    assert tool_names == {
        "read_job_description",
        "read_resume_section",
        "commit_to_strategy",
        "critique_draft",
        "save_letter",
    }


def test_agent_handles_tool_errors_gracefully(
    sample_user: UserProfile, sample_job: JobPosting, sample_resume: str
) -> None:
    # Malformed tool input — executor raises; loop reports back to Claude;
    # Claude then commits strategy, critiques, and saves.
    approved_json = _json.dumps(
        {"total": 100, "verdict": "approved", "priority_fixes": [], "scores": {}}
    )
    client = MagicMock()
    client.messages.create.side_effect = [
        _response([_tool_use_block("read_resume_section", {}, "id1")]),
        _response(
            [_tool_use_block(
                "commit_to_strategy",
                {
                    "fit_assessment": "MEDIUM",
                    "fit_reasoning": "Adjacent experience.",
                    "narrative_angle": "Production ML.",
                    "primary_project": "Some project.",
                },
                "id2",
            )]
        ),
        _response(
            [_tool_use_block("critique_draft", {"draft": _ok_letter()}, "id3")]
        ),
        _response([_text_block(approved_json)], stop_reason="end_turn"),
        _response(
            [_tool_use_block("save_letter", {"text": _ok_letter()}, "id4")]
        ),
    ]
    letter = generate_cover_letter_agent(
        user=sample_user,
        resume_text=sample_resume,
        job=sample_job,
        client=client,
    )
    assert "Header" in letter
