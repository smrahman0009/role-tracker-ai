"""DynamoDB-backed QueryStore.

Implements the same Protocol as JsonQueryStore but persists to a
DynamoDB table with shape:

    PK (HASH):   user_id   (S)
    SK (RANGE):  query_id  (S)

Item attributes:
    what          (S)
    where         (S)
    enabled       (Bool)
    created_at    (S)        ISO-8601 datetime

Creation order is preserved client-side: we sort by `created_at` after
the Query call. Random `query_id` strings would otherwise sort
alphabetically — meaningless to the user.

The YAML-bootstrap path that JsonQueryStore uses on first read is
intentionally NOT carried over: the cloud store starts empty and is
populated by the API. If you need to seed it, write a one-off script
that POSTs to /queries.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import boto3
from boto3.dynamodb.conditions import Key

from role_tracker.queries.models import SavedQuery


class DynamoDBQueryStore:
    """QueryStore backed by a DynamoDB table."""

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

    def list_queries(self, user_id: str) -> list[SavedQuery]:
        items = self._query_all(user_id)
        queries = [_item_to_query(it) for it in items]
        # Preserve "creation order" from the Protocol's contract.
        queries.sort(key=lambda q: q.created_at)
        return queries

    def get_query(self, user_id: str, query_id: str) -> SavedQuery | None:
        response = self._table.get_item(
            Key={"user_id": user_id, "query_id": query_id}
        )
        item = response.get("Item")
        return _item_to_query(item) if item else None

    # ----- Writes -----

    def add_query(self, user_id: str, what: str, where: str) -> SavedQuery:
        new = SavedQuery(
            query_id=uuid.uuid4().hex[:8],
            what=what.strip(),
            where=where.strip(),
            enabled=True,
            created_at=datetime.now(UTC),
        )
        self._table.put_item(
            Item={
                "user_id": user_id,
                "query_id": new.query_id,
                "what": new.what,
                "where": new.where,
                "enabled": new.enabled,
                "created_at": new.created_at.isoformat(),
            }
        )
        return new

    def update_query(
        self,
        user_id: str,
        query_id: str,
        *,
        what: str | None = None,
        where: str | None = None,
        enabled: bool | None = None,
    ) -> SavedQuery | None:
        # Build a dynamic UpdateExpression of only the fields the
        # caller passed. Skip the Update entirely if nothing changed.
        sets: list[str] = []
        names: dict[str, str] = {}
        values: dict[str, object] = {}

        if what is not None:
            sets.append("#what = :what")
            names["#what"] = "what"
            values[":what"] = what.strip()
        if where is not None:
            sets.append("#where = :where")
            names["#where"] = "where"
            values[":where"] = where.strip()
        if enabled is not None:
            sets.append("#enabled = :enabled")
            names["#enabled"] = "enabled"
            values[":enabled"] = enabled

        if not sets:
            return self.get_query(user_id, query_id)

        try:
            response = self._table.update_item(
                Key={"user_id": user_id, "query_id": query_id},
                UpdateExpression="SET " + ", ".join(sets),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ConditionExpression=(
                    "attribute_exists(user_id) AND attribute_exists(query_id)"
                ),
                ReturnValues="ALL_NEW",
            )
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            # Nothing matched the (user_id, query_id) pair — keep the
            # Protocol's "return None when missing" contract.
            return None

        return _item_to_query(response["Attributes"])

    def delete_query(self, user_id: str, query_id: str) -> bool:
        try:
            self._table.delete_item(
                Key={"user_id": user_id, "query_id": query_id},
                ConditionExpression=(
                    "attribute_exists(user_id) AND attribute_exists(query_id)"
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


def _item_to_query(item: dict) -> SavedQuery:
    return SavedQuery(
        query_id=item["query_id"],
        what=item["what"],
        where=item["where"],
        enabled=bool(item.get("enabled", True)),
        created_at=datetime.fromisoformat(item["created_at"]),
    )
