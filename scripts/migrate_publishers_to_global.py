"""One-shot migration: union all users' personal exclude_publishers
into the new global admin-managed list.

Run once after deploying the new backend code, before users start
hitting the new endpoints. Idempotent — safe to re-run.

What it does:
  1. Lists every user profile via the configured store.
  2. Reads each user's previous `exclude_publishers` value out of
     the raw stored payload (the field has been removed from the
     UserProfile pydantic model, so we go through the JSON blob).
  3. Unions everything (case-insensitive dedupe) with whatever's
     already in the global list.
  4. Saves the merged list back to the global store, attributing
     the change to "migration".

Usage:
    STORAGE_BACKEND=aws AWS_REGION=ca-central-1 \\
        uv run python scripts/migrate_publishers_to_global.py

In dev (file-backed stores) just run without env vars.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from role_tracker.config import Settings
from role_tracker.global_settings.factory import make_global_settings_store
from role_tracker.global_settings.models import GlobalHiddenPublishers


def main() -> int:
    settings = Settings()
    print(
        f"Storage backend: {settings.storage_backend!r}  "
        f"(STORAGE_BACKEND env var)"
    )

    publishers_by_user = _collect_per_user_publishers(settings)
    if not publishers_by_user:
        print("No legacy per-user exclude_publishers values found.")
    else:
        for user_id, items in publishers_by_user.items():
            print(f"  {user_id}: {items}")

    global_store = make_global_settings_store()
    current = global_store.get_hidden_publishers()
    print(f"\nCurrent global list ({len(current.publishers)} entries):")
    for p in current.publishers:
        print(f"  {p}")

    merged = _dedupe_case_insensitive(
        current.publishers
        + [p for items in publishers_by_user.values() for p in items]
    )
    if merged == current.publishers:
        print("\nNothing to migrate — global list already covers everything.")
        return 0

    new_value = GlobalHiddenPublishers(
        publishers=merged,
        updated_at=datetime.now(timezone.utc),
        updated_by="migration",
    )
    global_store.set_hidden_publishers(new_value)
    print(f"\nMerged global list ({len(merged)} entries):")
    for p in merged:
        print(f"  {p}")
    print("\nDone. Run again any time — it's idempotent.")
    return 0


# ----- Helpers -----------------------------------------------------------


def _collect_per_user_publishers(settings: Settings) -> dict[str, list[str]]:
    """Return {user_id: legacy_publishers_list} for every user that
    still has the deprecated field stored.

    Dives below the UserProfile model because the field has been
    removed; pydantic would silently drop it.
    """
    if settings.storage_backend == "aws":
        return _collect_from_dynamodb(settings)
    return _collect_from_yaml()


def _collect_from_dynamodb(settings: Settings) -> dict[str, list[str]]:
    import boto3

    table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(
        settings.ddb_users_table
    )
    out: dict[str, list[str]] = {}
    kwargs: dict = {}
    while True:
        response = table.scan(**kwargs)
        for item in response.get("Items", []):
            user_id = item.get("user_id", "<unknown>")
            payload = item.get("profile_json")
            if not isinstance(payload, str):
                continue
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            existing = data.get("exclude_publishers")
            if isinstance(existing, list) and existing:
                out[user_id] = [str(x) for x in existing]
        if "LastEvaluatedKey" not in response:
            break
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return out


def _collect_from_yaml() -> dict[str, list[str]]:
    import yaml
    from pathlib import Path

    users_dir = Path("users")
    if not users_dir.exists():
        return {}
    out: dict[str, list[str]] = {}
    for path in sorted(users_dir.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        existing = data.get("exclude_publishers")
        if isinstance(existing, list) and existing:
            out[path.stem] = [str(x) for x in existing]
    return out


def _dedupe_case_insensitive(items: list[str]) -> list[str]:
    """Preserve first-seen casing; drop duplicates and empties."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        cleaned = raw.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
