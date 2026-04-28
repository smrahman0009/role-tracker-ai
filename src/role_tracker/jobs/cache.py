"""Cache for the latest ranked-job snapshot per user.

Storage layout:
    data/jobs/{user_id}/snapshot.json

Holds the result of the last refresh (ranked ScoredJobs + when it ran).
The list endpoint reads from here; the refresh endpoint writes to here.

Phase 8 deploy: replace FileJobsCache with CosmosJobsCache. Routes don't
change — they depend on the Protocol, not the concrete class.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from role_tracker.jobs.models import JobPosting
from role_tracker.matching.scorer import ScoredJob

DEFAULT_ROOT = Path("data/jobs")


class StoredScoredJob(BaseModel):
    """Pydantic-serializable mirror of ScoredJob (which is a dataclass)."""

    job: JobPosting
    score: float

    @classmethod
    def from_scored(cls, s: ScoredJob) -> StoredScoredJob:
        return cls(job=s.job, score=s.score)

    def to_scored(self) -> ScoredJob:
        return ScoredJob(job=self.job, score=self.score)


class JobsSnapshot(BaseModel):
    """A user's most recent ranked-jobs result, persisted to disk."""

    last_refreshed_at: datetime
    jobs: list[StoredScoredJob]


class JobsCache(Protocol):
    def get_snapshot(self, user_id: str) -> JobsSnapshot | None: ...
    def save_snapshot(
        self, user_id: str, scored_jobs: list[ScoredJob]
    ) -> JobsSnapshot: ...


class FileJobsCache:
    """JobsCache backed by a JSON file per user."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def get_snapshot(self, user_id: str) -> JobsSnapshot | None:
        path = self._path(user_id)
        if not path.exists():
            return None
        return JobsSnapshot.model_validate(json.loads(path.read_text()))

    def save_snapshot(
        self, user_id: str, scored_jobs: list[ScoredJob]
    ) -> JobsSnapshot:
        snapshot = JobsSnapshot(
            last_refreshed_at=datetime.now(UTC),
            jobs=[StoredScoredJob.from_scored(s) for s in scored_jobs],
        )
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(snapshot.model_dump_json(indent=2) + "\n")
        tmp.replace(path)
        return snapshot

    def _path(self, user_id: str) -> Path:
        return self.root / user_id / "snapshot.json"
