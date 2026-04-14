#!/usr/bin/env python3
"""Fetch and print Canadian job postings from Adzuna.

Usage
-----
# Use queries defined in config.yaml (default):
    python scripts/run_fetch.py

# Pass one or more job titles directly (overrides config.yaml):
    python scripts/run_fetch.py --what "data scientist"
    python scripts/run_fetch.py --what "data engineer" --what "ML researcher"

# Override location (defaults to Canada):
    python scripts/run_fetch.py --what "data scientist" --where "toronto"
"""

import argparse

from role_tracker.config import JobQuery, Settings, load_job_filters
from role_tracker.jobs.adzuna import AdzunaClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Canadian job postings from Adzuna.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/run_fetch.py\n"
            '  python scripts/run_fetch.py --what "data scientist"\n'
            '  python scripts/run_fetch.py --what "data engineer" --what "ML researcher"\n'
            '  python scripts/run_fetch.py --what "data scientist" --where "toronto"\n'
        ),
    )
    parser.add_argument(
        "--what",
        metavar="TITLE",
        action="append",
        default=[],
        help="Job title / keyword to search. Repeatable. Omit to use config.yaml.",
    )
    parser.add_argument(
        "--where",
        metavar="LOCATION",
        default="canada",
        help='Location to search in (default: "canada").',
    )
    return parser.parse_args()


def print_jobs(client: AdzunaClient, queries: list[JobQuery], country: str, results_per_page: int) -> None:
    total = 0
    for query in queries:
        print(f"\n{'=' * 60}")
        print(f"  {query.what.upper()} | {query.where.title()}")
        print(f"{'=' * 60}")

        jobs = client.fetch_jobs(
            what=query.what,
            country=country,
            where=query.where,
            results_per_page=results_per_page,
        )

        if not jobs:
            print("  No results.")
            continue

        for i, job in enumerate(jobs, 1):
            salary = ""
            if job.salary_min and job.salary_max:
                salary = f"  Salary:   ${job.salary_min:,.0f} – ${job.salary_max:,.0f}\n"
            print(
                f"\n  {i}. {job.title}\n"
                f"  Company:  {job.company}\n"
                f"  Location: {job.location}\n"
                f"  Posted:   {job.posted_at[:10]}\n"
                f"{salary}"
                f"  URL:      {job.url}\n"
                f"  {job.description[:200].strip()}..."
            )
        total += len(jobs)

    print(f"\n{'=' * 60}")
    print(f"  Total jobs fetched: {total}")
    print(f"{'=' * 60}\n")


def main() -> None:
    args = parse_args()
    settings = Settings()
    filters = load_job_filters()
    client = AdzunaClient(app_id=settings.adzuna_app_id, app_key=settings.adzuna_app_key)

    if args.what:
        # CLI args override config.yaml
        queries = [JobQuery(what=w, where=args.where) for w in args.what]
    else:
        # Fall back to config.yaml queries
        queries = filters.queries

    print_jobs(client, queries, country=filters.country, results_per_page=filters.results_per_page)


if __name__ == "__main__":
    main()
