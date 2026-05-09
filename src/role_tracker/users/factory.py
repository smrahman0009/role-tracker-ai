"""UserProfileStore factory — picks YAML or DynamoDB based on Settings.

Centralised here so the four route call sites (letters, profile,
jobs x2) all resolve the same way without duplicating the
storage_backend branching logic.
"""

from __future__ import annotations

from role_tracker.config import Settings
from role_tracker.users.base import UserProfileStore
from role_tracker.users.yaml_store import YamlUserProfileStore


def make_user_profile_store(settings: Settings | None = None) -> UserProfileStore:
    """Return the configured UserProfileStore.

    `STORAGE_BACKEND=aws` → DynamoDBUserProfileStore (persistent across
    container restarts; what production uses). Anything else →
    YamlUserProfileStore (writes to ./users/*.yaml; what local dev
    uses). The two stores share the same Protocol so call sites
    don't notice the swap.
    """
    if settings is None:
        settings = Settings()
    if settings.storage_backend == "aws":
        from role_tracker.aws.dynamodb_user_profile_store import (
            DynamoDBUserProfileStore,
        )

        return DynamoDBUserProfileStore(
            table_name=settings.ddb_users_table,
            region_name=settings.aws_region,
        )
    return YamlUserProfileStore()
