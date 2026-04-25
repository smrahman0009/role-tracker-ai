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


def _commit_strategy(executors: dict) -> None:
    """Helper: commit a basic strategy so save/critique are unblocked."""
    executors["commit_to_strategy"](
        fit_assessment="HIGH",
        fit_reasoning="Resume matches all key requirements.",
        narrative_angle="Production NLP work maps to ranking and recommendation.",
        primary_project="Company Name Resolution pipeline",
    )


def _ok_letter() -> str:
    """A letter that passes deterministic checks (300+ words, paras <130)."""
    p1 = " ".join(["word"] * 100)
    p2 = " ".join(["word"] * 120)
    p3 = " ".join(["word"] * 100)
    return f"Header\n\nHello,\n\n{p1}\n\n{p2}\n\n{p3}\n\nBest,\nX"


def test_save_letter_requires_strategy(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, state = build_tool_executors(
        resume_text=sample_resume, job=sample_job
    )
    result = executors["save_letter"](text=_ok_letter())
    assert "no strategy committed" in result.lower()
    assert state["saved_letter"] is None


def test_save_letter_requires_critique(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, state = build_tool_executors(
        resume_text=sample_resume, job=sample_job
    )
    _commit_strategy(executors)
    result = executors["save_letter"](text=_ok_letter())
    assert "no critique" in result.lower()
    assert state["saved_letter"] is None


def test_save_letter_stores_in_state(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, state = build_tool_executors(
        resume_text=sample_resume, job=sample_job
    )
    _commit_strategy(executors)
    executors["critique_draft"](draft="anything")
    result = executors["save_letter"](text=_ok_letter())
    assert state["saved_letter"] is not None
    assert "saved" in result.lower()


def test_save_letter_rejects_too_short(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, state = build_tool_executors(
        resume_text=sample_resume, job=sample_job
    )
    _commit_strategy(executors)
    executors["critique_draft"](draft="anything")
    short_letter = "Hello,\n\nToo short.\n\nBest,\nX"
    result = executors["save_letter"](text=short_letter)
    assert "Refused" in result
    assert state["saved_letter"] is None


def test_save_letter_rejects_oversized_paragraph(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, _ = build_tool_executors(
        resume_text=sample_resume, job=sample_job
    )
    _commit_strategy(executors)
    executors["critique_draft"](draft="anything")
    massive_para = " ".join(["word"] * 200)
    bad_letter = f"Header\n\nHello,\n\n{massive_para}\n\nBest,\nX"
    result = executors["save_letter"](text=bad_letter)
    assert "Refused" in result
    assert "Paragraph" in result


def test_tool_call_count_increments(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, state = build_tool_executors(resume_text=sample_resume, job=sample_job)
    executors["read_job_description"]()
    executors["read_resume_section"](topic="Python")
    assert state["tool_call_count"] == 2


def test_critique_schema_is_exposed() -> None:
    names = {s["name"] for s in TOOL_SCHEMAS}
    assert "critique_draft" in names


def test_critique_without_client_auto_approves(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, state = build_tool_executors(
        resume_text=sample_resume, job=sample_job
    )
    _commit_strategy(executors)
    result = executors["critique_draft"](draft="Hello,\n\nBody.\n\nBest,\nX")
    assert "approved" in result
    assert state["critique_count"] == 1
    assert state["last_critique"]["verdict"] == "approved"


def test_critique_blocked_without_strategy(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, _ = build_tool_executors(
        resume_text=sample_resume, job=sample_job
    )
    result = executors["critique_draft"](draft="Hello\n\nBody\n\nBest,\nX")
    assert "before strategy" in result.lower()


def test_strategy_can_only_be_committed_once(
    sample_resume: str, sample_job: JobPosting
) -> None:
    executors, _ = build_tool_executors(
        resume_text=sample_resume, job=sample_job
    )
    _commit_strategy(executors)
    second = executors["commit_to_strategy"](
        fit_assessment="LOW",
        fit_reasoning="Different reasoning.",
        narrative_angle="Different angle.",
        primary_project="Different project.",
    )
    assert "already committed" in second.lower()


def test_critique_budget_cap(sample_resume: str, sample_job: JobPosting) -> None:
    from role_tracker.cover_letter.tools import MAX_CRITIQUES

    executors, _ = build_tool_executors(
        resume_text=sample_resume, job=sample_job
    )
    _commit_strategy(executors)
    for _ in range(MAX_CRITIQUES):
        executors["critique_draft"](draft="draft")
    result = executors["critique_draft"](draft="draft")
    assert "Max critiques" in result
