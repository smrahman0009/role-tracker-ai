"""Tracks asynchronous letter-generation tasks per user.

Same pattern as jobs/refresh_state.py: a JSON file per user holding records
for each generation task, with stale-task sweep on every read.

When a generation completes, the actual letter text is saved via the
LetterStore; this record only holds a pointer (job_id + saved_version).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

DEFAULT_ROOT = Path("data/letters")
STALE_AFTER_SECONDS = 5 * 60  # 5 minutes — same as the refresh sweep

LetterGenerationStatus = Literal["pending", "running", "done", "failed"]


class LetterGenerationRecord(BaseModel):
    """One generation task's persisted state."""

    generation_id: str
    job_id: str                          # the job this letter is for
    status: LetterGenerationStatus
    started_at: datetime
    completed_at: datetime | None = None
    saved_version: int | None = None     # populated when status="done"
    error: str | None = None             # populated when status="failed"
    # Human-readable progress label updated by the agent at each
    # tool-call iteration ("Reading the job description…", etc.).
    # The frontend renders this beneath the spinner so users can see
    # what the agent is currently doing. Defaults to a generic
    # starting message; routes update via mark_phase().
    phase: str = "Starting…"


class LetterGenerationStore(Protocol):
    def create(
        self, user_id: str, generation_id: str, job_id: str
    ) -> LetterGenerationRecord: ...
    def get(
        self, user_id: str, generation_id: str
    ) -> LetterGenerationRecord | None: ...
    def mark_running(self, user_id: str, generation_id: str) -> None: ...
    def mark_phase(
        self, user_id: str, generation_id: str, phase: str
    ) -> None: ...
    def mark_done(
        self, user_id: str, generation_id: str, saved_version: int
    ) -> None: ...
    def mark_failed(
        self, user_id: str, generation_id: str, error: str
    ) -> None: ...


class FileLetterGenerationStore:
    """Generation records persisted to data/letters/{user_id}/_generations.json."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def create(
        self, user_id: str, generation_id: str, job_id: str
    ) -> LetterGenerationRecord:
        record = LetterGenerationRecord(
            generation_id=generation_id,
            job_id=job_id,
            status="pending",
            started_at=datetime.now(UTC),
        )
        records = self._load(user_id)
        records.append(record)
        self._save(user_id, records)
        return record

    def get(
        self, user_id: str, generation_id: str
    ) -> LetterGenerationRecord | None:
        records = self._load(user_id)
        for r in records:
            if r.generation_id == generation_id:
                return self._sweep_if_stale(user_id, r, records)
        return None

    def mark_running(self, user_id: str, generation_id: str) -> None:
        self._update(user_id, generation_id, status="running")

    def mark_phase(
        self, user_id: str, generation_id: str, phase: str
    ) -> None:
        self._update(user_id, generation_id, phase=phase)

    def mark_done(
        self, user_id: str, generation_id: str, saved_version: int
    ) -> None:
        self._update(
            user_id,
            generation_id,
            status="done",
            completed_at=datetime.now(UTC),
            saved_version=saved_version,
        )

    def mark_failed(
        self, user_id: str, generation_id: str, error: str
    ) -> None:
        self._update(
            user_id,
            generation_id,
            status="failed",
            completed_at=datetime.now(UTC),
            error=error,
        )

    # ----- internals -----

    def _path(self, user_id: str) -> Path:
        return self.root / user_id / "_generations.json"

    def _load(self, user_id: str) -> list[LetterGenerationRecord]:
        path = self._path(user_id)
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return [LetterGenerationRecord(**r) for r in data.get("generations", [])]

    def _save(self, user_id: str, records: list[LetterGenerationRecord]) -> None:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        payload = {"generations": [r.model_dump(mode="json") for r in records]}
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(path)

    def _update(
        self, user_id: str, generation_id: str, **fields: object
    ) -> None:
        records = self._load(user_id)
        for i, r in enumerate(records):
            if r.generation_id == generation_id:
                records[i] = r.model_copy(update=fields)
                self._save(user_id, records)
                return

    def _sweep_if_stale(
        self,
        user_id: str,
        record: LetterGenerationRecord,
        all_records: list[LetterGenerationRecord],
    ) -> LetterGenerationRecord:
        if record.status != "running":
            return record
        age = datetime.now(UTC) - record.started_at
        if age <= timedelta(seconds=STALE_AFTER_SECONDS):
            return record
        updated = record.model_copy(
            update={
                "status": "failed",
                "completed_at": datetime.now(UTC),
                "error": (
                    "Generation timed out (likely server restart). "
                    "Please retry."
                ),
            }
        )
        for i, r in enumerate(all_records):
            if r.generation_id == record.generation_id:
                all_records[i] = updated
                break
        self._save(user_id, all_records)
        return updated
