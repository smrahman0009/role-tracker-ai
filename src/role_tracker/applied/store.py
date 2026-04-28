"""AppliedStore — tracks which jobs each user has marked as applied.

Stored as a JSON file per user containing a set of job_ids:
    data/applied/{user_id}.json
    {"applied": ["job_id_1", "job_id_2", ...]}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

DEFAULT_ROOT = Path("data/applied")


class AppliedStore(Protocol):
    def is_applied(self, user_id: str, job_id: str) -> bool: ...
    def list_applied(self, user_id: str) -> set[str]: ...
    def mark_applied(self, user_id: str, job_id: str) -> bool:
        """Returns True if newly applied, False if already was."""
        ...

    def unmark_applied(self, user_id: str, job_id: str) -> bool:
        """Returns True if removed, False if wasn't there."""
        ...


class FileAppliedStore:
    """File-backed AppliedStore."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def is_applied(self, user_id: str, job_id: str) -> bool:
        return job_id in self._load(user_id)

    def list_applied(self, user_id: str) -> set[str]:
        return self._load(user_id)

    def mark_applied(self, user_id: str, job_id: str) -> bool:
        applied = self._load(user_id)
        if job_id in applied:
            return False
        applied.add(job_id)
        self._save(user_id, applied)
        return True

    def unmark_applied(self, user_id: str, job_id: str) -> bool:
        applied = self._load(user_id)
        if job_id not in applied:
            return False
        applied.discard(job_id)
        self._save(user_id, applied)
        return True

    # ----- internals -----

    def _path(self, user_id: str) -> Path:
        return self.root / f"{user_id}.json"

    def _load(self, user_id: str) -> set[str]:
        path = self._path(user_id)
        if not path.exists():
            return set()
        data = json.loads(path.read_text())
        return set(data.get("applied", []))

    def _save(self, user_id: str, applied: set[str]) -> None:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        # Sort for deterministic file content (helps git diffs if anyone
        # accidentally commits these — though `data/` is gitignored).
        payload = {"applied": sorted(applied)}
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(path)
