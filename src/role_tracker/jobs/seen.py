"""SeenJobsStore — persistent index of every job we've ever shown the user.

The cache snapshot represents the *current view* (the most recent
refresh or ad-hoc search). Detail / letter routes need a place that
remembers jobs *across* views, so opening yesterday's job after running
a new search today still works.

Storage layout:
    data/seen_jobs/{user_id}.json
    {"jobs": [StoredScoredJob, ...]}

Upsert semantics: when the same job_id is seen again with a different
score (different search), the latest entry wins. A future enhancement
could keep per-search scores; for now the latest is good enough.

Phase 7 deploy: replaces with CosmosSeenJobsStore. Routes depend on the
Protocol, not the concrete class.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from role_tracker.jobs.cache import StoredScoredJob
from role_tracker.matching.scorer import ScoredJob

DEFAULT_ROOT = Path("data/seen_jobs")


class SeenJobsStore(Protocol):
    def get(self, user_id: str, job_id: str) -> StoredScoredJob | None: ...
    def upsert_many(self, user_id: str, scored: list[ScoredJob]) -> None: ...
    def remove(self, user_id: str, job_id: str) -> bool:
        """Delete one job. Returns True if removed, False if it wasn't there."""
        ...


class FileSeenJobsStore:
    """JSON-backed SeenJobsStore."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def get(self, user_id: str, job_id: str) -> StoredScoredJob | None:
        for entry in self._load(user_id):
            if entry.job.id == job_id:
                return entry
        return None

    def upsert_many(self, user_id: str, scored: list[ScoredJob]) -> None:
        if not scored:
            return
        existing = {e.job.id: e for e in self._load(user_id)}
        for s in scored:
            existing[s.job.id] = StoredScoredJob.from_scored(s)
        self._save(user_id, list(existing.values()))

    def remove(self, user_id: str, job_id: str) -> bool:
        existing = self._load(user_id)
        kept = [e for e in existing if e.job.id != job_id]
        if len(kept) == len(existing):
            return False
        self._save(user_id, kept)
        return True

    # ----- internals -----

    def _path(self, user_id: str) -> Path:
        return self.root / f"{user_id}.json"

    def _load(self, user_id: str) -> list[StoredScoredJob]:
        path = self._path(user_id)
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return [StoredScoredJob.model_validate(j) for j in data.get("jobs", [])]

    def _save(self, user_id: str, entries: list[StoredScoredJob]) -> None:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        payload = {"jobs": [e.model_dump(mode="json") for e in entries]}
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(path)
