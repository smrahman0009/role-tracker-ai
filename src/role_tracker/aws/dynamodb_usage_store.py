"""DynamoDB-backed UsageStore.

Implements the same Protocol as FileUsageStore but persists to a
DynamoDB table. The table shape (set up by infra/03-dynamodb.sh):

    PK (HASH):   user_id     (S)
    SK (RANGE):  year_month  (S)   "YYYY-MM"

Item attributes:
    jsearch_calls         Number — total JSearch fetch calls this month
    f_<feature>           Number — count for one feature, one attribute each
                                   (e.g. f_embedding, f_cover_letter_generate)

Why one attribute per feature instead of a nested map: DynamoDB's
`ADD` operator atomically increments a top-level numeric attribute
and creates it if it doesn't exist. Atomic + concurrent-safe with no
read-modify-write — perfect for a counter. Nested-map increments
require multi-step expressions and can race.

Reads reconstruct the MonthlyUsage model by scanning attributes whose
names start with `f_` and stripping the prefix.
"""

from __future__ import annotations

from datetime import UTC, datetime

import boto3
from boto3.dynamodb.conditions import Key

from role_tracker.usage.store import MonthlyUsage, cost_of_features

# Prefix used for per-feature counters. Picked to be both human-
# readable in the AWS console and unambiguous against any future
# top-level fields we might add.
_FEATURE_ATTR_PREFIX = "f_"

# Per-day per-feature counters. Attribute name shape:
#   d_<YYYY-MM-DD>__<feature>     e.g.  d_2026-05-07__cover_letter_draft
# Two underscores between the date and feature so the date prefix is
# unambiguously parseable even if a feature name ever contained an
# underscore (which they all do).
_DAILY_ATTR_PREFIX = "d_"
_DAILY_SEPARATOR = "__"


def _current_year_month() -> str:
    now = datetime.now(UTC)
    return f"{now.year:04d}-{now.month:02d}"


def _today_iso() -> str:
    now = datetime.now(UTC)
    return f"{now.year:04d}-{now.month:02d}-{now.day:02d}"


def _daily_attr(date_iso: str, feature: str) -> str:
    return f"{_DAILY_ATTR_PREFIX}{date_iso}{_DAILY_SEPARATOR}{feature}"


class DynamoDBUsageStore:
    """UsageStore backed by a DynamoDB table."""

    def __init__(
        self,
        table_name: str,
        *,
        region_name: str | None = None,
        dynamodb_resource: object | None = None,
    ) -> None:
        # `dynamodb_resource` is injectable for tests (moto provides a
        # fake resource we want to bind to). In production we let
        # boto3 build one against the real AWS endpoint.
        if dynamodb_resource is None:
            dynamodb_resource = boto3.resource(
                "dynamodb", region_name=region_name
            )
        self._table = dynamodb_resource.Table(table_name)

    # ----- Reads -----

    def get_month(self, user_id: str, year_month: str) -> MonthlyUsage:
        response = self._table.get_item(
            Key={"user_id": user_id, "year_month": year_month}
        )
        item = response.get("Item")
        if not item:
            return MonthlyUsage(year_month=year_month)
        return _item_to_monthly(item)

    def list_months(self, user_id: str) -> list[MonthlyUsage]:
        # Query all months for one user, newest first. Pagination is
        # only relevant if a user has > 1MB of data, which they won't
        # for ~6 months of small counters — but we handle it anyway
        # so the code is correct under load.
        items: list[dict] = []
        kwargs = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "ScanIndexForward": False,  # newest year_month first
        }
        while True:
            response = self._table.query(**kwargs)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        return [_item_to_monthly(item) for item in items]

    # ----- Writes (atomic, race-safe) -----

    def record_jsearch(self, user_id: str) -> None:
        self._table.update_item(
            Key={"user_id": user_id, "year_month": _current_year_month()},
            UpdateExpression="ADD jsearch_calls :one",
            ExpressionAttributeValues={":one": 1},
        )

    def record_feature(self, user_id: str, feature: str) -> None:
        # Single atomic update bumps both the monthly counter and
        # today's per-day counter. `ADD` on a non-existent attribute
        # creates it; on a non-existent item creates the item.
        # Concurrent callers all increment correctly — DynamoDB
        # serialises ADDs server-side.
        self._table.update_item(
            Key={"user_id": user_id, "year_month": _current_year_month()},
            UpdateExpression="ADD #monthly :one, #daily :one",
            ExpressionAttributeNames={
                "#monthly": f"{_FEATURE_ATTR_PREFIX}{feature}",
                "#daily": _daily_attr(_today_iso(), feature),
            },
            ExpressionAttributeValues={":one": 1},
        )

    def get_today_cost_usd(self, user_id: str) -> float:
        response = self._table.get_item(
            Key={"user_id": user_id, "year_month": _current_year_month()}
        )
        item = response.get("Item")
        if not item:
            return 0.0
        today = _today_iso()
        prefix = f"{_DAILY_ATTR_PREFIX}{today}{_DAILY_SEPARATOR}"
        today_calls: dict[str, int] = {
            key[len(prefix):]: int(value)
            for key, value in item.items()
            if key.startswith(prefix)
        }
        return cost_of_features(today_calls)


def _item_to_monthly(item: dict) -> MonthlyUsage:
    """Translate a raw DynamoDB item back into a MonthlyUsage model."""
    feature_calls: dict[str, int] = {}
    daily: dict[str, dict[str, int]] = {}
    for key, value in item.items():
        if key.startswith(_FEATURE_ATTR_PREFIX) and not key.startswith(
            _DAILY_ATTR_PREFIX
        ):
            feature_calls[key[len(_FEATURE_ATTR_PREFIX):]] = int(value)
        elif key.startswith(_DAILY_ATTR_PREFIX):
            rest = key[len(_DAILY_ATTR_PREFIX):]
            if _DAILY_SEPARATOR not in rest:
                continue
            date_iso, feature = rest.split(_DAILY_SEPARATOR, 1)
            daily.setdefault(date_iso, {})[feature] = int(value)

    return MonthlyUsage(
        year_month=item["year_month"],
        jsearch_calls=int(item.get("jsearch_calls", 0)),
        feature_calls=feature_calls,
        daily_feature_calls=daily,
    )
