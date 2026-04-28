"""LetterStore — persistence for saved letter versions per (user, job).

Storage layout:
    data/letters/{user_id}/{job_id}.json
    {"versions": [StoredLetter dicts, ...]}

One file per (user, job). All versions held inline. Versions are 1-based
and monotonically increasing — when adding a new letter, the store assigns
`max(existing) + 1`.

This is independent from the Phase 4 CLI's `data/cover_letters/` layout.
The CLI keeps writing folders for human review; the API uses this JSON
format because it's queryable. We can converge later (after Cosmos lands)
by writing both locations or migrating one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from role_tracker.letters.models import StoredLetter

DEFAULT_ROOT = Path("data/letters")


class LetterStore(Protocol):
    def list_versions(self, user_id: str, job_id: str) -> list[StoredLetter]: ...
    def get_version(
        self, user_id: str, job_id: str, version: int
    ) -> StoredLetter | None: ...
    def save_letter(
        self,
        user_id: str,
        job_id: str,
        *,
        text: str,
        strategy: dict | None,
        critique: dict | None,
        feedback_used: str | None = None,
    ) -> StoredLetter: ...


class FileLetterStore:
    """LetterStore backed by JSON files on disk."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def list_versions(self, user_id: str, job_id: str) -> list[StoredLetter]:
        return self._load(user_id, job_id)

    def get_version(
        self, user_id: str, job_id: str, version: int
    ) -> StoredLetter | None:
        for letter in self._load(user_id, job_id):
            if letter.version == version:
                return letter
        return None

    def save_letter(
        self,
        user_id: str,
        job_id: str,
        *,
        text: str,
        strategy: dict | None,
        critique: dict | None,
        feedback_used: str | None = None,
    ) -> StoredLetter:
        existing = self._load(user_id, job_id)
        next_version = max((letter.version for letter in existing), default=0) + 1
        letter = StoredLetter(
            job_id=job_id,
            version=next_version,
            text=text,
            word_count=len(text.split()),
            strategy=strategy,
            critique=critique,
            feedback_used=feedback_used,
            created_at=datetime.now(UTC),
        )
        existing.append(letter)
        self._save(user_id, job_id, existing)
        return letter

    # ----- internals -----

    def _path(self, user_id: str, job_id: str) -> Path:
        # Job IDs may contain "/" or "==" — sanitize for filesystem.
        safe_job = job_id.replace("/", "_").replace("=", "_")
        return self.root / user_id / f"{safe_job}.json"

    def _load(self, user_id: str, job_id: str) -> list[StoredLetter]:
        path = self._path(user_id, job_id)
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return [StoredLetter(**v) for v in data.get("versions", [])]

    def _save(
        self, user_id: str, job_id: str, versions: list[StoredLetter]
    ) -> None:
        path = self._path(user_id, job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        payload = {
            "versions": [v.model_dump(mode="json") for v in versions],
        }
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(path)
