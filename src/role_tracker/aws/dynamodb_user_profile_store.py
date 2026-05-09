"""DynamoDB-backed UserProfileStore.

Implements the same Protocol as YamlUserProfileStore but persists
the profile in a single DynamoDB item per user — so profile edits
made through the Settings UI survive container restarts (whereas
the YAML store wrote inside the ephemeral container filesystem).

Table shape:

    PK (HASH):   user_id   (S)
    (no SK — one item per user)

The whole UserProfile is serialised to JSON and stored under the
`profile_json` attribute. Storing the JSON blob (rather than
flattening every field to its own attribute) means schema changes
to UserProfile don't require a DynamoDB migration — pydantic's
model_validate handles backward / forward compat.

Trade-off: you can't query by individual fields (e.g. "find users
with city=Toronto"). Acceptable here because we never do that —
all reads are by `user_id`, and `list_users()` is rare and small.
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3

from role_tracker.users.models import UserProfile


class UserProfileNotFoundError(LookupError):
    """Raised by get_user when no row exists for a user_id. Mirrors the
    FileNotFoundError that YamlUserProfileStore raises."""


class DynamoDBUserProfileStore:
    """UserProfileStore backed by a DynamoDB table."""

    def __init__(
        self,
        table_name: str,
        *,
        region_name: str | None = None,
        dynamodb_resource: object | None = None,
    ) -> None:
        if dynamodb_resource is None:
            dynamodb_resource = boto3.resource(
                "dynamodb", region_name=region_name
            )
        self._table = dynamodb_resource.Table(table_name)

    # ----- Reads ----------------------------------------------------

    def list_users(self) -> list[UserProfile]:
        # Scan is acceptable here because the user count is tiny (3
        # in current production, 50 max for the foreseeable future).
        # If this ever grows, replace with a GSI on a constant
        # partition key.
        items: list[dict] = []
        kwargs: dict = {}
        while True:
            response = self._table.scan(**kwargs)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        profiles = [_item_to_profile(it) for it in items]
        # Sort by id for stable test output and predictable Settings
        # listings.
        profiles.sort(key=lambda p: p.id)
        return profiles

    def get_user(self, user_id: str) -> UserProfile:
        response = self._table.get_item(Key={"user_id": user_id})
        item = response.get("Item")
        if item is None:
            raise UserProfileNotFoundError(
                f"No user profile in DynamoDB for user_id={user_id!r}"
            )
        return _item_to_profile(item)

    # ----- Writes ---------------------------------------------------

    def save_user(self, profile: UserProfile) -> None:
        """Persist (or overwrite) a profile."""
        # Mode "json" so Path objects (resume_path) round-trip as
        # strings rather than blowing up on json.dumps.
        profile_json = json.dumps(profile.model_dump(mode="json"))
        self._table.put_item(
            Item={
                "user_id": profile.id,
                "profile_json": profile_json,
            }
        )


def _item_to_profile(item: dict) -> UserProfile:
    payload = json.loads(item["profile_json"])
    # resume_path is typed as Path in the model but stored as a
    # string. Pydantic's coercion handles the round-trip when we
    # validate, but explicit Path makes intent clearer for any
    # future reader.
    if isinstance(payload.get("resume_path"), str):
        payload["resume_path"] = Path(payload["resume_path"])
    return UserProfile.model_validate(payload)
