#!/usr/bin/env python3
"""Smoke test for Phase 4 Step 3 — run the agent on the Shopify job."""

from anthropic import Anthropic
from dotenv import load_dotenv

from role_tracker.cover_letter.agent import generate_cover_letter_agent
from role_tracker.cover_letter.storage import build_letter_dir, save_letter_bundle
from role_tracker.jobs.models import JobPosting
from role_tracker.resume.parser import parse_resume
from role_tracker.users.yaml_store import YamlUserProfileStore

# Same Shopify job we used for the Step 1 baseline, so we can compare.
SAMPLE_JOB = JobPosting(
    id="jsearch_shopify_agent_001",
    title="Staff Machine Learning Engineer",
    company="Shopify",
    location="Toronto, Ontario",
    description=(
        "We're looking for a Staff Machine Learning Engineer to join our Ranking & "
        "Recommendations team. You'll own end-to-end ML systems for personalization, "
        "mentor senior engineers, and drive architectural decisions. "
        "Required: 7+ years "
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
    load_dotenv()
    store = YamlUserProfileStore()
    user = store.get_user("smrah")
    resume_text = parse_resume(user.resume_path)

    print(f"\n{'=' * 60}")
    print("  AGENT RUN — Shopify Staff ML Engineer")
    print(f"{'=' * 60}\n")

    client = Anthropic()
    usage: dict = {}
    letter = generate_cover_letter_agent(
        user=user,
        resume_text=resume_text,
        job=SAMPLE_JOB,
        client=client,
        usage_tracker=usage,
    )

    print("\nToken usage (main agent):")
    print(f"  Uncached input: {usage.get('uncached_input', 0):,}")
    print(f"  Cache writes:   {usage.get('cache_writes', 0):,}")
    print(f"  Cache reads:    {usage.get('cache_reads', 0):,}")
    total_prefix = usage.get("cache_reads", 0) + usage.get("cache_writes", 0)
    if total_prefix:
        hit_rate = usage["cache_reads"] / total_prefix * 100
        print(f"  Cache hit rate: {hit_rate:.1f}%")

    folder = build_letter_dir("smrah", SAMPLE_JOB)
    save_letter_bundle(
        folder=folder,
        letter_text=letter,
        job=SAMPLE_JOB,
        resume_text=resume_text,
        strategy=usage.get("strategy"),
        critique=usage.get("last_critique"),
    )

    if usage.get("strategy"):
        s = usage["strategy"]
        print("\nAgent strategy:")
        print(f"  Fit:      {s.get('fit_assessment')}")
        print(f"  Angle:    {s.get('narrative_angle')}")
        print(f"  Primary:  {s.get('primary_project')}")
        print(f"  Secondary: {s.get('secondary_project') or '(none)'}")
    if usage.get("last_critique"):
        c = usage["last_critique"]
        print(f"\nFinal critique: {c.get('total', '?')}/110 — {c.get('verdict', '?')}")

    print("\nSaved to:", folder)
    print("\n  open '" + str(folder) + "'\n")


if __name__ == "__main__":
    main()
