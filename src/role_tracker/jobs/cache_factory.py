"""JobsCache factory — picks File or DynamoDB based on Settings.

Mirrors users/factory.py. Centralised so the jobs route call sites
all resolve the same way without duplicating the storage_backend
branching.
"""

from __future__ import annotations

from role_tracker.config import Settings
from role_tracker.jobs.cache import FileJobsCache, JobsCache


def make_jobs_cache(settings: Settings | None = None) -> JobsCache:
    """Return the configured JobsCache.

    `STORAGE_BACKEND=aws` → DynamoDBJobsCache (snapshot survives
    container restarts; what production needs). Anything else →
    FileJobsCache (writes to ./data/jobs/{user}/snapshot.json; local
    dev). Same Protocol so call sites don't notice the swap.
    """
    if settings is None:
        settings = Settings()
    if settings.storage_backend == "aws":
        from role_tracker.aws.dynamodb_jobs_cache import DynamoDBJobsCache

        return DynamoDBJobsCache(
            table_name=settings.ddb_jobs_table,
            region_name=settings.aws_region,
        )
    return FileJobsCache()
