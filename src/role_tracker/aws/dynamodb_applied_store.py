"""DynamoDB-backed AppliedStore.

Implements the same Protocol as FileAppliedStore but persists to a
DynamoDB table with shape:

    PK (HASH):   user_id   (S)
    SK (RANGE):  job_id    (S)

Item attributes (all optional except the keys):
    applied_at            (S)        ISO-8601 datetime
    resume_filename       (S)
    resume_sha256         (S)
    letter_version_used   (N)

The legacy `{"applied": [...]}` shape that FileAppliedStore had to
handle isn't relevant here — the cloud store starts empty and is
written to from the API only.
"""

from __future__ import annotations

from datetime import UTC, datetime

import boto3
from boto3.dynamodb.conditions import Key

from role_tracker.applied.store import ApplicationRecord


class DynamoDBAppliedStore:
    """AppliedStore backed by a DynamoDB table."""

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

    # ----- Reads -----

    def is_applied(self, user_id: str, job_id: str) -> bool:
        # ProjectionExpression keeps the response small — we only need
        # to know whether the item exists.
        response = self._table.get_item(
            Key={"user_id": user_id, "job_id": job_id},
            ProjectionExpression="job_id",
        )
        return "Item" in response

    def list_applied(self, user_id: str) -> dict[str, ApplicationRecord]:
        items = self._query_all(user_id)
        return {item["job_id"]: _item_to_record(item) for item in items}

    def get_application(
        self, user_id: str, job_id: str
    ) -> ApplicationRecord | None:
        response = self._table.get_item(
            Key={"user_id": user_id, "job_id": job_id}
        )
        item = response.get("Item")
        return _item_to_record(item) if item else None

    # ----- Writes -----

    def mark_applied(
        self,
        user_id: str,
        job_id: str,
        *,
        resume_filename: str = "",
        resume_sha256: str = "",
        letter_version_used: int | None = None,
    ) -> bool:
        # Detect "newly applied" by inspecting the previous item via
        # ReturnValues=ALL_OLD on the put. Single round-trip, atomic.
        item: dict[str, object] = {
            "user_id": user_id,
            "job_id": job_id,
            "applied_at": datetime.now(UTC).isoformat(),
            "resume_filename": resume_filename,
            "resume_sha256": resume_sha256,
        }
        if letter_version_used is not None:
            item["letter_version_used"] = letter_version_used

        response = self._table.put_item(
            Item=item,
            ReturnValues="ALL_OLD",
        )
        was_new = "Attributes" not in response
        return was_new

    def unmark_applied(self, user_id: str, job_id: str) -> bool:
        response = self._table.delete_item(
            Key={"user_id": user_id, "job_id": job_id},
            ReturnValues="ALL_OLD",
        )
        return "Attributes" in response

    # ----- internals -----

    def _query_all(self, user_id: str) -> list[dict]:
        items: list[dict] = []
        kwargs = {"KeyConditionExpression": Key("user_id").eq(user_id)}
        while True:
            response = self._table.query(**kwargs)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        return items


def _item_to_record(item: dict) -> ApplicationRecord:
    applied_at_raw = item.get("applied_at")
    applied_at = (
        datetime.fromisoformat(applied_at_raw) if applied_at_raw else None
    )
    letter_version = item.get("letter_version_used")
    return ApplicationRecord(
        applied_at=applied_at,
        resume_filename=item.get("resume_filename", ""),
        resume_sha256=item.get("resume_sha256", ""),
        letter_version_used=int(letter_version) if letter_version is not None else None,
    )
