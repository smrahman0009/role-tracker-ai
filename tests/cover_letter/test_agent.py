"""Tests for the agentic cover-letter generator. Mocked Anthropic client."""

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
    """Build a mock tool_use content block that matches Anthropic's shape."""
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


def test_agent_completes_on_save_letter(
    sample_user: UserProfile, sample_job: JobPosting, sample_resume: str
) -> None:
    # Simulated Claude flow: read JD → read resume → critique → save.
    # The critique tool also calls client.messages.create internally (for Haiku),
    # so we need one extra text response in the mock sequence.
    import json as _json

    approved_json = _json.dumps(
        {"total": 92, "verdict": "approved", "priority_fixes": [], "scores": {}}
    )
    client = MagicMock()
    client.messages.create.side_effect = [
        _response([_tool_use_block("read_job_description", {})]),
        _response(
            [_tool_use_block(
                "read_resume_section", {"topic": "transformers"}, "id2"
            )]
        ),
        _response(
            [_tool_use_block(
                "critique_draft",
                {"draft": "Hello,\n\nDraft body.\n\nBest,\nShaikh"},
                "id3",
            )]
        ),
        # Internal call by the critique tool (returns JSON verdict).
        _response([_text_block(approved_json)], stop_reason="end_turn"),
        _response(
            [_tool_use_block(
                "save_letter",
                {"text": "Hello,\n\nFinal letter body.\n\nBest,\nShaikh"},
                "id4",
            )]
        ),
    ]

    letter = generate_cover_letter_agent(
        user=sample_user,
        resume_text=sample_resume,
        job=sample_job,
        client=client,
    )
    assert letter.startswith("Hello,")
    assert "Best" in letter
    # 4 agent iterations + 1 internal critique call = 5
    assert client.messages.create.call_count == 5


def test_agent_raises_on_no_save(
    sample_user: UserProfile, sample_job: JobPosting, sample_resume: str
) -> None:
    # Claude ends turn without saving — that's an error.
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
            [_tool_use_block("save_letter", {"text": "Hello\n\nX\n\nBest,\nY"})]
        ),
    ]
    generate_cover_letter_agent(
        user=sample_user,
        resume_text=sample_resume,
        job=sample_job,
        client=client,
    )
    kwargs = client.messages.create.call_args.kwargs
    tool_names = {t["name"] for t in kwargs["tools"]}
    assert tool_names == {
        "read_job_description",
        "read_resume_section",
        "critique_draft",
        "save_letter",
    }


def test_agent_handles_tool_errors_gracefully(
    sample_user: UserProfile, sample_job: JobPosting, sample_resume: str
) -> None:
    # Agent sends a malformed tool input; executor raises; loop reports error
    # back to Claude and Claude then saves a valid letter.
    client = MagicMock()
    client.messages.create.side_effect = [
        # Missing "topic" — will raise TypeError in the executor.
        _response([_tool_use_block("read_resume_section", {}, "id1")]),
        _response(
            [
                _tool_use_block(
                    "save_letter",
                    {"text": "Hello\n\nBody\n\nBest,\nName"},
                    "id2",
                )
            ]
        ),
    ]
    letter = generate_cover_letter_agent(
        user=sample_user,
        resume_text=sample_resume,
        job=sample_job,
        client=client,
    )
    assert "Hello" in letter
