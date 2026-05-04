"""DynamoDB-backed LetterStore.

Implements the same Protocol as FileLetterStore but persists to a
DynamoDB table with a compound sort key:

    PK (HASH):   user_id      (S)
    SK (RANGE):  job_version  (S)   "{sanitized_job_id}#{version:04d}"

Why a compound sort key: it lets us answer "all versions for one job"
with a single Query + begins_with(SK, "{job_id}#"), and "version N
of job X" with a Get on the exact key.

Item attributes:
    job_id              (S)   redundant with the SK, kept for the
                              StoredLetter model's job_id field
    version             (N)
    text                (S)
    word_count          (N)
    strategy            (M)   nullable
    critique            (M)   nullable
    feedback_used       (S)   nullable
    refinement_index    (N)
    edited_by_user      (Bool)
    created_at          (S)   ISO-8601

Job IDs may contain "/" or "=" (base64-ish), so we sanitize the same
way FileLetterStore does to keep sort keys predictable.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from role_tracker.letters.models import StoredLetter


def _to_dynamodb_value(value: Any) -> Any:
    """DynamoDB rejects Python floats — round-trip via JSON-with-Decimal
    so nested dicts (strategy, critique) coming from arbitrary JSON
    sources land correctly."""
    if value is None:
        return None
    return json.loads(json.dumps(value), parse_float=Decimal)


def _from_dynamodb_value(value: Any) -> Any:
    """Round-trip Decimal back to float / int on read."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        # Integer-valued Decimals become ints; everything else becomes float.
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: _from_dynamodb_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb_value(v) for v in value]
    return value

_VERSION_PAD = 4
_SEPARATOR = "#"


def _sanitize_job_id(job_id: str) -> str:
    return job_id.replace("/", "_").replace("=", "_").replace(_SEPARATOR, "_")


def _make_sort_key(job_id: str, version: int) -> str:
    return f"{_sanitize_job_id(job_id)}{_SEPARATOR}{version:0{_VERSION_PAD}d}"


def _job_id_prefix(job_id: str) -> str:
    return f"{_sanitize_job_id(job_id)}{_SEPARATOR}"


class DynamoDBLetterStore:
    """LetterStore backed by a DynamoDB table."""

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

    def list_versions(self, user_id: str, job_id: str) -> list[StoredLetter]:
        items = self._query_versions(user_id, job_id)
        return [_item_to_letter(item) for item in items]

    def get_version(
        self, user_id: str, job_id: str, version: int
    ) -> StoredLetter | None:
        response = self._table.get_item(
            Key={
                "user_id": user_id,
                "job_version": _make_sort_key(job_id, version),
            }
        )
        item = response.get("Item")
        return _item_to_letter(item) if item else None

    def count_refinements(self, user_id: str, job_id: str) -> int:
        items = self._query_versions(user_id, job_id)
        return max(
            (int(item.get("refinement_index", 0)) for item in items),
            default=0,
        )

    # ----- Writes -----

    def save_letter(
        self,
        user_id: str,
        job_id: str,
        *,
        text: str,
        strategy: dict | None,
        critique: dict | None,
        feedback_used: str | None = None,
        refinement_index: int = 0,
        edited_by_user: bool = False,
    ) -> StoredLetter:
        # Determine next version. Single-user app — no concurrent saves
        # in practice, so a non-atomic read-then-write is acceptable.
        existing = self._query_versions(user_id, job_id)
        next_version = (
            max(int(item.get("version", 0)) for item in existing)
            if existing
            else 0
        ) + 1

        letter = StoredLetter(
            job_id=job_id,
            version=next_version,
            text=text,
            word_count=len(text.split()),
            strategy=strategy,
            critique=critique,
            feedback_used=feedback_used,
            refinement_index=refinement_index,
            edited_by_user=edited_by_user,
            created_at=datetime.now(UTC),
        )

        item: dict[str, object] = {
            "user_id": user_id,
            "job_version": _make_sort_key(job_id, next_version),
            "job_id": job_id,
            "version": next_version,
            "text": text,
            "word_count": letter.word_count,
            "refinement_index": refinement_index,
            "edited_by_user": edited_by_user,
            "created_at": letter.created_at.isoformat(),
        }
        if strategy is not None:
            item["strategy"] = _to_dynamodb_value(strategy)
        if critique is not None:
            item["critique"] = _to_dynamodb_value(critique)
        if feedback_used is not None:
            item["feedback_used"] = feedback_used

        self._table.put_item(Item=item)
        return letter

    def delete_all_versions(self, user_id: str, job_id: str) -> None:
        items = self._query_versions(user_id, job_id)
        if not items:
            return
        with self._table.batch_writer() as batch:
            for item in items:
                batch.delete_item(
                    Key={
                        "user_id": user_id,
                        "job_version": item["job_version"],
                    }
                )

    # ----- internals -----

    def _query_versions(self, user_id: str, job_id: str) -> list[dict]:
        items: list[dict] = []
        kwargs = {
            "KeyConditionExpression": (
                Key("user_id").eq(user_id)
                & Key("job_version").begins_with(_job_id_prefix(job_id))
            ),
        }
        while True:
            response = self._table.query(**kwargs)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        return items


def _item_to_letter(item: dict) -> StoredLetter:
    return StoredLetter(
        job_id=item["job_id"],
        version=int(item["version"]),
        text=item["text"],
        word_count=int(item["word_count"]),
        strategy=_from_dynamodb_value(item.get("strategy")),
        critique=_from_dynamodb_value(item.get("critique")),
        feedback_used=item.get("feedback_used"),
        refinement_index=int(item.get("refinement_index", 0)),
        edited_by_user=bool(item.get("edited_by_user", False)),
        created_at=datetime.fromisoformat(item["created_at"]),
    )
