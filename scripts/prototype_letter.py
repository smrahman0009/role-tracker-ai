#!/usr/bin/env python3
"""Quick smoke test for Phase 4 Step 1 — generates one letter and saves to disk."""

from pathlib import Path

from dotenv import load_dotenv

from anthropic import Anthropic

from role_tracker.cover_letter.generator import generate_cover_letter
from role_tracker.cover_letter.storage import build_letter_dir, save_letter_bundle
from role_tracker.jobs.models import JobPosting
from role_tracker.resume.parser import parse_resume
from role_tracker.users.yaml_store import YamlUserProfileStore

# Sample job — realistic data from JSearch
SAMPLE_JOB = JobPosting(
    id="jsearch_shopify_001",
    title="Staff Machine Learning Engineer",
    company="Shopify",
    location="Toronto, Ontario",
    description=(
        "We're looking for a Staff Machine Learning Engineer to join our Ranking & "
        "Recommendations team. You'll own end-to-end ML systems for personalization, "
        "mentor senior engineers, and drive architectural decisions. Required: 7+ years "
        "ML engineering, deep PyTorch expertise, large-scale recommender systems. "
        "We use Kubernetes, Python, and distributed training at scale."
    ),
    url="https://shopify.com/careers/staff-ml-engineer",
    posted_at="2026-04-20T10:00:00Z",
    salary_min=180000,
    salary_max=240000,
    source="jsearch",
    publisher="Shopify Careers",
)


def main() -> None:
    # Load environment variables from .env
    load_dotenv()

    # Load user and resume
    store = YamlUserProfileStore()
    user = store.get_user("smrah")
    resume_text = parse_resume(user.resume_path)

    # Generate letter
    print(f"\n{'='*60}")
    print(f"  Generating cover letter for {SAMPLE_JOB.title} @ {SAMPLE_JOB.company}")
    print(f"{'='*60}\n")
    client = Anthropic()
    letter = generate_cover_letter(
        user=user,
        resume_text=resume_text,
        job=SAMPLE_JOB,
        client=client,
    )

    # Save to disk
    folder = build_letter_dir("smrah", SAMPLE_JOB)
    save_letter_bundle(
        folder=folder,
        letter_text=letter,
        job=SAMPLE_JOB,
        resume_text=resume_text,
    )

    print(f"\n{'='*60}")
    print(f"  Letter saved!")
    print(f"{'='*60}")
    print(f"\nFolder: {folder}")
    print(f"\nContents:")
    print(f"  - cover_letter.md")
    print(f"  - job_description.md")
    print(f"  - resume_snapshot.txt")
    print(f"\nOpen the folder to review:\n")
    print(f"  open '{folder}'")
    print()


if __name__ == "__main__":
    main()
