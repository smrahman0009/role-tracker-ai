#!/usr/bin/env python3
"""Fetch and print Canadian job postings from Adzuna. Phase 2 smoke script."""

from role_tracker.config import Settings, load_job_filters
from role_tracker.jobs.adzuna import AdzunaClient


def main() -> None:
    settings = Settings()
    filters = load_job_filters()
    client = AdzunaClient(app_id=settings.adzuna_app_id, app_key=settings.adzuna_app_key)

    total = 0
    for query in filters.queries:
        print(f"\n{'=' * 60}")
        print(f"  {query.what.upper()} | {query.where.title()}")
        print(f"{'=' * 60}")

        jobs = client.fetch_jobs(
            what=query.what,
            country=filters.country,
            where=query.where,
            results_per_page=filters.results_per_page,
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


if __name__ == "__main__":
    main()
