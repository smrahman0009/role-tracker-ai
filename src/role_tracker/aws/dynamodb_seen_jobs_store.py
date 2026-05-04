"""DynamoDB-backed SeenJobsStore.

Implements the same Protocol as FileSeenJobsStore. Each (user, job)
pair is one item:

    PK (HASH):   user_id   (S)
    SK (RANGE):  job_id    (S)
    posting     (M)        nested map mirroring JobPosting
    score       (N)        cosine similarity to the user's resume

`upsert_many` uses BatchWriteItem in chunks of 25 (DynamoDB's per-call
ceiling) so a daily refresh that fans out 50–100 candidates lands in
3–5 writes total instead of N round-trips.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from role_tracker.jobs.cache import StoredScoredJob
from role_tracker.matching.scorer import ScoredJob


def _to_dynamodb(value: Any) -> Any:
    """Floats → Decimal recursively (DynamoDB rejects floats)."""
    return json.loads(json.dumps(value), parse_float=Decimal)


def _from_dynamodb(value: Any) -> Any:
    """Decimal → int / float recursively (Pydantic expects native types)."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: _from_dynamodb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb(v) for v in value]
    return value


class DynamoDBSeenJobsStore:
    """SeenJobsStore backed by a DynamoDB table."""

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

    def get(self, user_id: str, job_id: str) -> StoredScoredJob | None:
        response = self._table.get_item(
            Key={"user_id": user_id, "job_id": job_id}
        )
        item = response.get("Item")
        return _item_to_stored(item) if item else None

    def list_all(self, user_id: str) -> list[StoredScoredJob]:
        items = self._query_all(user_id)
        return [_item_to_stored(it) for it in items]

    # ----- Writes -----

    def upsert_many(self, user_id: str, scored: list[ScoredJob]) -> None:
        if not scored:
            return
        with self._table.batch_writer() as batch:
            for s in scored:
                stored = StoredScoredJob.from_scored(s)
                batch.put_item(
                    Item={
                        "user_id": user_id,
                        "job_id": stored.job.id,
                        "posting": _to_dynamodb(
                            stored.job.model_dump(mode="json")
                        ),
                        "score": _to_dynamodb(stored.score),
                    }
                )

    def remove(self, user_id: str, job_id: str) -> bool:
        try:
            self._table.delete_item(
                Key={"user_id": user_id, "job_id": job_id},
                ConditionExpression=(
                    "attribute_exists(user_id) AND attribute_exists(job_id)"
                ),
            )
            return True
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False

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


def _item_to_stored(item: dict) -> StoredScoredJob:
    posting = _from_dynamodb(item.get("posting", {}))
    score = _from_dynamodb(item.get("score", 0))
    return StoredScoredJob.model_validate({"job": posting, "score": score})
