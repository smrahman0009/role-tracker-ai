"""Tests for the Step 1 naive generator — mocked Anthropic client."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from role_tracker.cover_letter.generator import (
    MODEL,
    REFERENCE_LETTER,
    SYSTEM_PROMPT,
    generate_cover_letter,
)
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
        linkedin_url="https://linkedin.com/in/smrah",
        github_url="https://github.com/smrah",
        resume_path=Path("data/resumes/smrah.pdf"),
        queries=[],
    )


@pytest.fixture
def sample_job() -> JobPosting:
    return JobPosting(
        id="jsearch_abc123",
        title="Staff Machine Learning Engineer",
        company="Shopify",
        location="Toronto, Ontario",
        description=(
            "Build recommender systems at scale using PyTorch. "
            "Experience with transformer models required."
        ),
        url="https://shopify.com/careers/42",
        posted_at="2026-04-20T10:00:00.000Z",
        source="jsearch",
        publisher="Shopify Careers",
    )


def _mock_client(returned_text: str) -> MagicMock:
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = returned_text
    response = MagicMock()
    response.content = [text_block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


def test_returns_letter_text(sample_user: UserProfile, sample_job: JobPosting) -> None:
    client = _mock_client("Hello,\n\nThis is the letter body.\n\nBest,\nShaikh")
    letter = generate_cover_letter(
        user=sample_user,
        resume_text="Resume: transformers, Azure Functions.",
        job=sample_job,
        client=client,
    )
    assert letter.startswith("Hello,")
    assert "Best," in letter


def test_calls_sonnet_with_system_prompt(
    sample_user: UserProfile, sample_job: JobPosting
) -> None:
    client = _mock_client("letter")
    generate_cover_letter(
        user=sample_user,
        resume_text="Resume: transformers.",
        job=sample_job,
        client=client,
    )
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == MODEL
    assert call_kwargs["system"] == SYSTEM_PROMPT


def test_user_message_includes_resume_and_job(
    sample_user: UserProfile, sample_job: JobPosting
) -> None:
    client = _mock_client("letter")
    generate_cover_letter(
        user=sample_user,
        resume_text="RESUME_MARKER_XYZ",
        job=sample_job,
        client=client,
    )
    user_msg = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "RESUME_MARKER_XYZ" in user_msg
    assert "Shopify" in user_msg
    assert "Staff Machine Learning Engineer" in user_msg
    assert "recommender systems" in user_msg


def test_user_message_includes_reference_letter_and_header(
    sample_user: UserProfile, sample_job: JobPosting
) -> None:
    client = _mock_client("letter")
    generate_cover_letter(
        user=sample_user, resume_text="x", job=sample_job, client=client
    )
    user_msg = client.messages.create.call_args.kwargs["messages"][0]["content"]
    # Style example is present
    assert REFERENCE_LETTER.strip()[:50] in user_msg
    # Header block rendered from the user profile
    assert "Shaikh Mushfikur Rahman" in user_msg
    assert "782-882-0852" in user_msg
    assert "Halifax, NS" in user_msg


def test_concatenates_multiple_text_blocks(
    sample_user: UserProfile, sample_job: JobPosting
) -> None:
    # Anthropic can split a reply into multiple text blocks — we must join them.
    block_a, block_b = MagicMock(), MagicMock()
    block_a.type = "text"
    block_a.text = "Hello,\n\n"
    block_b.type = "text"
    block_b.text = "Part two.\n\nBest,\nShaikh"
    response = MagicMock()
    response.content = [block_a, block_b]
    client = MagicMock()
    client.messages.create.return_value = response

    letter = generate_cover_letter(
        user=sample_user, resume_text="x", job=sample_job, client=client
    )
    assert "Part two" in letter
    assert letter.startswith("Hello,")
