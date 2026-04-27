"""Tests for cover-letter on-disk layout."""

from datetime import date
from pathlib import Path

import pytest

from role_tracker.cover_letter.storage import (
    build_letter_dir,
    letter_folder_name,
    save_letter_bundle,
    slugify,
)
from role_tracker.jobs.models import JobPosting


@pytest.fixture
def sample_job() -> JobPosting:
    return JobPosting(
        id="jsearch_abc123def456",
        title="Staff Machine Learning Engineer",
        company="Shopify",
        location="Toronto, Ontario",
        description="Build recommender systems.",
        url="https://shopify.com/careers/42",
        posted_at="2026-04-20T10:00:00.000Z",
        salary_min=180000,
        salary_max=240000,
        source="jsearch",
        publisher="Shopify Careers",
    )


def test_slugify_lowercases_and_hyphenates() -> None:
    assert slugify("Shopify Inc.") == "shopify-inc"
    assert slugify("  Staff ML Engineer  ") == "staff-ml-engineer"
    assert slugify("A&B Co / Remote!") == "a-b-co-remote"


def test_slugify_falls_back_for_empty() -> None:
    assert slugify("") == "untitled"
    assert slugify("///---") == "untitled"


def test_slugify_truncates() -> None:
    long = "a" * 200
    assert len(slugify(long, max_len=40)) == 40


def test_letter_folder_name_is_date_first_and_readable(sample_job: JobPosting) -> None:
    name = letter_folder_name(sample_job, today=date(2026, 4, 22))
    assert name == "2026-04-22_shopify_staff-machine-learning-engineer_def456"


def test_folder_name_uses_hash_for_same_day_dupes(sample_job: JobPosting) -> None:
    twin = sample_job.model_copy(update={"id": "jsearch_xyz789"})
    a = letter_folder_name(sample_job, today=date(2026, 4, 22))
    b = letter_folder_name(twin, today=date(2026, 4, 22))
    assert a != b


def test_build_letter_dir_creates_folder(
    tmp_path: Path, sample_job: JobPosting
) -> None:
    folder = build_letter_dir(
        "smrah", sample_job, root=tmp_path, today=date(2026, 4, 22)
    )
    assert folder.exists() and folder.is_dir()
    assert folder.parent.name == "smrah"
    assert folder.name.startswith("2026-04-22_shopify_")


def test_save_letter_bundle_writes_three_files(
    tmp_path: Path, sample_job: JobPosting
) -> None:
    folder = build_letter_dir(
        "smrah", sample_job, root=tmp_path, today=date(2026, 4, 22)
    )
    save_letter_bundle(
        folder=folder,
        letter_text="Hello,\n\nThis is the letter.\n\nBest,\nName",
        job=sample_job,
        resume_text="Resume text here.",
    )
    assert (folder / "cover_letter.md").read_text().startswith("Hello,")
    assert "Shopify" in (folder / "job_description.md").read_text()
    assert "Toronto" in (folder / "job_description.md").read_text()
    assert "Resume text here" in (folder / "resume_snapshot.txt").read_text()


def test_jd_snapshot_includes_salary_when_present(
    tmp_path: Path, sample_job: JobPosting
) -> None:
    folder = build_letter_dir("smrah", sample_job, root=tmp_path)
    save_letter_bundle(
        folder=folder, letter_text="x", job=sample_job, resume_text="y"
    )
    jd = (folder / "job_description.md").read_text()
    assert "$180,000" in jd
    assert "$240,000" in jd


def test_jd_snapshot_omits_salary_when_missing(tmp_path: Path) -> None:
    job = JobPosting(
        id="no-salary",
        title="ML Engineer",
        company="Acme",
        location="Remote",
        description="x",
        url="https://acme.com",
        posted_at="2026-04-22T00:00:00Z",
        source="jsearch",
        publisher="Acme Careers",
    )
    folder = build_letter_dir("smrah", job, root=tmp_path)
    save_letter_bundle(folder=folder, letter_text="x", job=job, resume_text="y")
    assert "Salary" not in (folder / "job_description.md").read_text()
