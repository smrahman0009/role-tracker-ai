"""DynamoDB-backed JobsCache.

Implements the same Protocol as FileJobsCache but persists the
snapshot in a single DynamoDB item per user — so the ranked-jobs
list survives container restarts (the FileJobsCache wrote inside
the ephemeral container filesystem, so every deploy wiped it).

Table shape:

    PK (HASH):   user_id        (S)
    (no SK — one snapshot item per user)

The whole JobsSnapshot is serialised to JSON and stored under the
`snapshot_json` attribute. Storing the JSON blob (rather than a
nested DynamoDB map) keeps schema changes to JobsSnapshot free —
pydantic's model_validate_json handles backward / forward compat —
and sidesteps DynamoDB's float→Decimal coercion entirely.

Trade-off: you can't query by individual fields. Acceptable here —
all reads are by user_id, one item each.
"""

from __future__ import annotations

from datetime import UTC, datetime

import boto3

from role_tracker.jobs.cache import JobsSnapshot, StoredScoredJob
from role_tracker.matching.scorer import ScoredJob


class DynamoDBJobsCache:
    """JobsCache backed by a DynamoDB table (one item per user)."""

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

    def get_snapshot(self, user_id: str) -> JobsSnapshot | None:
        response = self._table.get_item(Key={"user_id": user_id})
        item = response.get("Item")
        if item is None:
            return None
        return JobsSnapshot.model_validate_json(item["snapshot_json"])

    # ----- Writes ---------------------------------------------------

    def save_snapshot(
        self,
        user_id: str,
        scored_jobs: list[ScoredJob],
        *,
        candidates_seen: int = 0,
        queries_run: int = 0,
        top_n_cap: int = 0,
    ) -> JobsSnapshot:
        snapshot = JobsSnapshot(
            last_refreshed_at=datetime.now(UTC),
            jobs=[StoredScoredJob.from_scored(s) for s in scored_jobs],
            candidates_seen=candidates_seen,
            queries_run=queries_run,
            top_n_cap=top_n_cap,
        )
        self._table.put_item(
            Item={
                "user_id": user_id,
                "snapshot_json": snapshot.model_dump_json(),
            }
        )
        return snapshot

    def clear_snapshot(self, user_id: str) -> bool:
        """Delete the cached snapshot. Returns True if one existed.

        Only touches the snapshot — seen_jobs, applied records,
        letters, and usage counters live in other tables and are
        unaffected, so anything the user has acted on is preserved.
        """
        response = self._table.delete_item(
            Key={"user_id": user_id},
            ReturnValues="ALL_OLD",
        )
        return response.get("Attributes") is not None
