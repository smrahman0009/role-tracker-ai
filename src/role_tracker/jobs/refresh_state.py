"""Tracks asynchronous "refresh jobs" tasks per user.

Each POST /jobs/refresh creates a record. The actual work runs as a
FastAPI BackgroundTask; the frontend polls GET /jobs/refresh/{id} which
reads the record's status.

Storage layout:
    data/jobs/{user_id}/refreshes.json
    {"refreshes": [RefreshRecord, ...]}

Stale-task sweep: any record stuck on status="running" with started_at
older than STALE_AFTER_SECONDS gets auto-marked failed when it's read.
This handles the App Service F1 case where the backend may sleep or
restart mid-task, killing the in-memory background work but leaving
the record stuck.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

DEFAULT_ROOT = Path("data/jobs")
STALE_AFTER_SECONDS = 5 * 60  # 5 minutes

RefreshStatus = Literal["pending", "running", "done", "failed"]


class RefreshRecord(BaseModel):
    """One refresh task's persisted state."""

    refresh_id: str
    status: RefreshStatus
    started_at: datetime
    completed_at: datetime | None = None
    jobs_added: int | None = None
    candidates_seen: int | None = None
    queries_run: int | None = None
    error: str | None = None


class RefreshTaskStore(Protocol):
    def create(self, user_id: str, refresh_id: str) -> RefreshRecord: ...
    def get(self, user_id: str, refresh_id: str) -> RefreshRecord | None: ...
    def mark_running(self, user_id: str, refresh_id: str) -> None: ...
    def mark_done(
        self,
        user_id: str,
        refresh_id: str,
        jobs_added: int,
        *,
        candidates_seen: int = 0,
        queries_run: int = 0,
    ) -> None: ...
    def mark_failed(self, user_id: str, refresh_id: str, error: str) -> None: ...


class FileRefreshTaskStore:
    """Refresh records persisted as a list of dicts in one JSON file per user."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    # ---- Protocol surface ----

    def create(self, user_id: str, refresh_id: str) -> RefreshRecord:
        record = RefreshRecord(
            refresh_id=refresh_id,
            status="pending",
            started_at=datetime.now(UTC),
        )
        records = self._load(user_id)
        records.append(record)
        self._save(user_id, records)
        return record

    def get(self, user_id: str, refresh_id: str) -> RefreshRecord | None:
        records = self._load(user_id)
        for r in records:
            if r.refresh_id == refresh_id:
                return self._sweep_if_stale(user_id, r, records)
        return None

    def mark_running(self, user_id: str, refresh_id: str) -> None:
        self._update(user_id, refresh_id, status="running")

    def mark_done(
        self,
        user_id: str,
        refresh_id: str,
        jobs_added: int,
        *,
        candidates_seen: int = 0,
        queries_run: int = 0,
    ) -> None:
        self._update(
            user_id,
            refresh_id,
            status="done",
            completed_at=datetime.now(UTC),
            jobs_added=jobs_added,
            candidates_seen=candidates_seen,
            queries_run=queries_run,
        )

    def mark_failed(self, user_id: str, refresh_id: str, error: str) -> None:
        self._update(
            user_id,
            refresh_id,
            status="failed",
            completed_at=datetime.now(UTC),
            error=error,
        )

    # ---- internals ----

    def _path(self, user_id: str) -> Path:
        return self.root / user_id / "refreshes.json"

    def _load(self, user_id: str) -> list[RefreshRecord]:
        path = self._path(user_id)
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return [RefreshRecord(**r) for r in data.get("refreshes", [])]

    def _save(self, user_id: str, records: list[RefreshRecord]) -> None:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        payload = {"refreshes": [r.model_dump(mode="json") for r in records]}
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(path)

    def _update(self, user_id: str, refresh_id: str, **fields: object) -> None:
        records = self._load(user_id)
        for i, r in enumerate(records):
            if r.refresh_id == refresh_id:
                records[i] = r.model_copy(update=fields)
                self._save(user_id, records)
                return

    def _sweep_if_stale(
        self,
        user_id: str,
        record: RefreshRecord,
        all_records: list[RefreshRecord],
    ) -> RefreshRecord:
        """If this record is stuck on 'running' and old, auto-mark failed."""
        if record.status != "running":
            return record
        age = datetime.now(UTC) - record.started_at
        if age <= timedelta(seconds=STALE_AFTER_SECONDS):
            return record
        # Sweep stale.
        updated = record.model_copy(
            update={
                "status": "failed",
                "completed_at": datetime.now(UTC),
                "error": (
                    "Refresh timed out (likely server restart). "
                    "Please retry."
                ),
            }
        )
        for i, r in enumerate(all_records):
            if r.refresh_id == record.refresh_id:
                all_records[i] = updated
                break
        self._save(user_id, all_records)
        return updated
