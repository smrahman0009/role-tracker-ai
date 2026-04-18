#!/usr/bin/env python3
"""Daily job-matching pipeline — runs per-user against JSearch.

Usage
-----
# Run all users in users/ :
    python scripts/run_match.py

# Run one user only:
    python scripts/run_match.py --user smrah

# Override that user's queries ad-hoc:
    python scripts/run_match.py --user smrah --what "data scientist"

# Override fetch size + top-N:
    python scripts/run_match.py --user smrah --limit 30 --top-n 10
"""

import argparse

from role_tracker.config import (
    JobQuery,
    PipelineDefaults,
    Settings,
    load_pipeline_defaults,
)
from role_tracker.jobs.base import JobSource
from role_tracker.jobs.filters import apply_exclusions
from role_tracker.jobs.jsearch import JSearchClient
from role_tracker.jobs.models import JobPosting
from role_tracker.matching.embeddings import Embedder, load_or_embed_resume
from role_tracker.matching.scorer import (
    ScoredJob,
    job_to_embedding_text,
    rank_jobs,
)
from role_tracker.resume.parser import parse_resume
from role_tracker.users.base import UserProfileStore
from role_tracker.users.models import UserProfile
from role_tracker.users.yaml_store import YamlUserProfileStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the job-matching pipeline for one or all users.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--user",
        metavar="ID",
        default=None,
        help="Run only this user (default: all users in users/).",
    )
    parser.add_argument(
        "--what",
        metavar="TITLE",
        action="append",
        default=[],
        help="Override the user's queries. Repeatable. Requires --user.",
    )
    parser.add_argument(
        "--where",
        metavar="LOCATION",
        default="canada",
        help='Location override (used with --what). Default "canada".',
    )
    parser.add_argument(
        "--limit",
        metavar="N",
        type=int,
        default=None,
        help="Max results per query (default: from config.yaml).",
    )
    parser.add_argument(
        "--top-n",
        metavar="N",
        type=int,
        default=None,
        help="Override the user's top_n_jobs.",
    )
    parser.add_argument(
        "--show-excluded",
        action="store_true",
        help="Print the list of jobs dropped by the filter.",
    )
    return parser.parse_args()


def fetch_all(
    sources: list[JobSource], queries: list[JobQuery], limit: int
) -> list[JobPosting]:
    """Fetch every query from every source, dedupe by (title, company)."""
    seen: dict[tuple[str, str], JobPosting] = {}
    for source in sources:
        for query in queries:
            try:
                jobs = source.fetch_jobs(
                    what=query.what, where=query.where, limit=limit
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [!] {source.name} failed for '{query.what}': {exc}")
                continue
            for job in jobs:
                key = (job.title.strip().lower(), job.company.strip().lower())
                seen.setdefault(key, job)
    return list(seen.values())


def build_sources(
    settings: Settings, country: str, exclude_publishers: list[str]
) -> list[JobSource]:
    if not settings.jsearch_rapidapi_key:
        raise SystemExit(
            "JSEARCH_RAPIDAPI_KEY is missing from .env. "
            "Get a key at https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch"
        )
    return [
        JSearchClient(
            rapidapi_key=settings.jsearch_rapidapi_key,
            country=country,
            exclude_publishers=exclude_publishers,
        )
    ]


def pick_users(store: UserProfileStore, user_id: str | None) -> list[UserProfile]:
    if user_id:
        return [store.get_user(user_id)]
    users = store.list_users()
    if not users:
        raise SystemExit(
            "No user profiles found in users/. Create one (e.g. users/alice.yaml)."
        )
    return users


def print_scored(scored: list[ScoredJob]) -> None:
    print(f"\n{'=' * 60}")
    print(f"  TOP {len(scored)} MATCHES")
    print(f"{'=' * 60}")
    for i, s in enumerate(scored, 1):
        salary = ""
        if s.job.salary_min and s.job.salary_max:
            salary = (
                f"  Salary:    ${s.job.salary_min:,.0f} – "
                f"${s.job.salary_max:,.0f}\n"
            )
        print(
            f"\n{'-' * 60}\n"
            f"  #{i}   Match score: {s.score:.3f}\n"
            f"{'-' * 60}\n"
            f"  Title:     {s.job.title}\n"
            f"  Company:   {s.job.company}\n"
            f"  Location:  {s.job.location}\n"
            f"  Posted:    {s.job.posted_at[:10]}\n"
            f"  Publisher: {s.job.publisher}\n"
            f"{salary}"
            f"  URL:       {s.job.url}\n"
            f"\n  Description:\n  {s.job.description.strip()}"
        )
    print(f"\n{'=' * 60}\n")


def run_for_user(
    user: UserProfile,
    sources: list[JobSource],
    embedder: Embedder,
    defaults: PipelineDefaults,
    args: argparse.Namespace,
) -> None:
    print(f"\n{'#' * 60}\n#  User: {user.name} ({user.id})\n{'#' * 60}")

    if args.what and args.user:
        queries = [JobQuery(what=w, where=args.where) for w in args.what]
    else:
        queries = user.queries

    limit = args.limit if args.limit is not None else defaults.results_per_page
    top_n = args.top_n if args.top_n is not None else user.top_n_jobs

    print(f"Parsing resume: {user.resume_path}")
    resume_text = parse_resume(user.resume_path)

    print("Embedding resume (cached on disk if unchanged)...")
    resume_vector = load_or_embed_resume(
        embedder, resume_text, user.resume_embedding_cache_path
    )

    noun = "query" if len(queries) == 1 else "queries"
    print(f"Fetching jobs for {len(queries)} {noun}...")
    jobs = fetch_all(sources, queries, limit=limit)
    print(f"Fetched {len(jobs)} unique jobs.")

    jobs, excluded = apply_exclusions(
        jobs,
        exclude_companies=user.exclude_companies,
        exclude_title_keywords=user.exclude_title_keywords,
        exclude_publishers=user.exclude_publishers,
    )
    print(f"Filtered out {len(excluded)} jobs (per user's exclusion list).")
    if args.show_excluded and excluded:
        print("\n  Excluded:")
        for e in excluded:
            print(f"    - [{e.reason}] {e.job.title} @ {e.job.company}")

    if not jobs:
        print("No jobs to score after filtering.")
        return

    print(f"Embedding {len(jobs)} jobs...")
    job_vectors = embedder.embed([job_to_embedding_text(j) for j in jobs])

    scored = rank_jobs(resume_vector, jobs, job_vectors, top_n=top_n)
    print_scored(scored)


def main() -> None:
    args = parse_args()

    if args.what and not args.user:
        raise SystemExit("--what requires --user (can't apply overrides to all users)")

    settings = Settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is missing from .env")

    defaults = load_pipeline_defaults()
    store = YamlUserProfileStore()
    users = pick_users(store, args.user)

    embedder = Embedder(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )

    for user in users:
        # Per-user sources so each user's exclude_publishers is honoured
        # server-side (JSearch filters before we ever see the bad listing).
        sources = build_sources(
            settings,
            country=defaults.country,
            exclude_publishers=user.exclude_publishers,
        )
        run_for_user(user, sources, embedder, defaults, args)


if __name__ == "__main__":
    main()
