"""GlobalSettingsStore factory — JSON in dev, DynamoDB in prod.

Mirrors users/factory.py; same STORAGE_BACKEND env knob picks the
backend. Centralised so route handlers and CLI tools can resolve
the configured store without duplicating the branching.
"""

from __future__ import annotations

from role_tracker.config import Settings
from role_tracker.global_settings.base import GlobalSettingsStore
from role_tracker.global_settings.json_store import JsonGlobalSettingsStore


def make_global_settings_store(
    settings: Settings | None = None,
) -> GlobalSettingsStore:
    """Return the configured GlobalSettingsStore."""
    if settings is None:
        settings = Settings()
    if settings.storage_backend == "aws":
        from role_tracker.aws.dynamodb_global_settings_store import (
            DynamoDBGlobalSettingsStore,
        )

        return DynamoDBGlobalSettingsStore(
            table_name=settings.ddb_global_settings_table,
            region_name=settings.aws_region,
        )
    return JsonGlobalSettingsStore()
