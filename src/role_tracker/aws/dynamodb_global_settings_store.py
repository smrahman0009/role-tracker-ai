"""DynamoDB-backed GlobalSettingsStore.

Same Protocol as JsonGlobalSettingsStore but persists each document
as a single item keyed by document name. One table is plenty —
admin-managed settings are tiny and rarely change.

Table shape:

    PK (HASH):   setting_name   (S)
    (no SK — one item per setting)

Document body is stored as JSON under the `value_json` attribute
to keep schema migrations free.
"""

from __future__ import annotations

import json

import boto3

from role_tracker.global_settings.models import GlobalHiddenPublishers

_HIDDEN_PUBLISHERS_KEY = "hidden_publishers"


class DynamoDBGlobalSettingsStore:
    """GlobalSettingsStore backed by a single DynamoDB table."""

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

    def get_hidden_publishers(self) -> GlobalHiddenPublishers:
        response = self._table.get_item(
            Key={"setting_name": _HIDDEN_PUBLISHERS_KEY}
        )
        item = response.get("Item")
        if item is None:
            return GlobalHiddenPublishers()
        return GlobalHiddenPublishers.model_validate_json(item["value_json"])

    # ----- Writes ---------------------------------------------------

    def set_hidden_publishers(self, value: GlobalHiddenPublishers) -> None:
        self._table.put_item(
            Item={
                "setting_name": _HIDDEN_PUBLISHERS_KEY,
                "value_json": json.dumps(value.model_dump(mode="json")),
            }
        )
