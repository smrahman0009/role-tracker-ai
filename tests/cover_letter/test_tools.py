"""Tests for cover-letter agent tools."""

import pytest

from role_tracker.cover_letter.tools import TOOL_SCHEMAS, build_tool_executors
from role_tracker.jobs.models import JobPosting


@pytest.fixture
def sample_job() -> JobPosting:
    return JobPosting(
        id="abc",
        title="Staff ML Engineer",
        company="Shopify",
        location="Toronto",
        description="Build recommender systems with PyTorch at scale.",
        url="https://shopify.com/careers/1",
        posted_at="2026-04-22T00:00:00Z",
        salary_min=180000,
        salary_max=240000,
        source="jsearch",
        publisher="Shopify Careers",
    )


@pytest.fixture
def sample_resume() -> str:
    return (
        "SUMMARY\n"
        "Data Scientist with transformer experience.\n\n"
        "TECHNICAL SKILLS\n"
        "Python, PyTorch, Azure Functions, Docker.\n\n"
        "EXPERIENCE\n"
        "Data Scientist at Everstream Analytics — 92% accuracy on NLP pipeline.\n\n"
        "EDUCATION\n"
        "Master of Digital Innovation at Dalhousie."
    )


def test_tool_schemas_have_required_fields() -> None:
    for schema in TOOL_SCHEMAS:
        assert "name" in schema
        assert "description" in schema
        assert "input_schema" in schema
        assert schema["input_schema"]["type"] == "object"


def test_read_job_description_returns_formatted_jd(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, _ = build_tool_executors(resume_text=sample_resume, job=sample_job)
    result = executors["read_job_description"]()
    assert "Shopify" in result
    assert "Staff ML Engineer" in result
    assert "recommender systems" in result
    assert "$180,000" in result


def test_read_resume_section_matches_keyword(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, _ = build_tool_executors(resume_text=sample_resume, job=sample_job)
    result = executors["read_resume_section"](topic="PyTorch")
    assert "PyTorch" in result


def test_read_resume_section_case_insensitive(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, _ = build_tool_executors(resume_text=sample_resume, job=sample_job)
    result = executors["read_resume_section"](topic="pytorch")
    assert "PyTorch" in result


def test_read_resume_section_returns_helpful_miss(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, _ = build_tool_executors(resume_text=sample_resume, job=sample_job)
    result = executors["read_resume_section"](topic="blockchain")
    assert "No resume content" in result
    assert "blockchain" in result


def test_save_letter_stores_in_state(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, state = build_tool_executors(
        resume_text=sample_resume, job=sample_job
    )
    result = executors["save_letter"](
        text="Hello,\n\nThis is the letter.\n\nBest,\nName"
    )
    assert state["saved_letter"].startswith("Hello,")
    assert "words" in result
    assert "complete" in result


def test_tool_call_count_increments(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, state = build_tool_executors(resume_text=sample_resume, job=sample_job)
    executors["read_job_description"]()
    executors["read_resume_section"](topic="Python")
    assert state["tool_call_count"] == 2
