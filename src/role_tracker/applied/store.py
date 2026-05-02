"""AppliedStore — tracks each user's applications as rich records.

Storage shape (per user, JSON file at data/applied/{user_id}.json):

  {
    "applications": {
      "<job_id>": {
        "applied_at":           "2026-04-30T14:00:00Z",
        "resume_filename":      "shaikh_v3.pdf",
        "resume_sha256":        "5fa3...",
        "letter_version_used":  3
      },
      ...
    }
  }

Backwards-compat: legacy files used to be `{"applied": ["id1", "id2"]}`
(set-of-job-ids). On read we accept both shapes and synthesise empty
records for the legacy IDs (timestamps come back as None on those).
That means no migration script is needed; legacy applications display
"—" for the new fields and any newly-toggled application uses the
rich shape from then on.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

DEFAULT_ROOT = Path("data/applied")


class ApplicationRecord(BaseModel):
    """One application's audit data — captured at the moment the user
    clicks Mark Applied."""

    applied_at: datetime | None = None
    resume_filename: str = ""
    resume_sha256: str = ""
    letter_version_used: int | None = None


class AppliedStore(Protocol):
    def is_applied(self, user_id: str, job_id: str) -> bool: ...
    def list_applied(self, user_id: str) -> dict[str, ApplicationRecord]: ...
    def get_application(
        self, user_id: str, job_id: str
    ) -> ApplicationRecord | None: ...
    def mark_applied(
        self,
        user_id: str,
        job_id: str,
        *,
        resume_filename: str = "",
        resume_sha256: str = "",
        letter_version_used: int | None = None,
    ) -> bool:
        """Returns True if newly applied, False if already was."""
        ...

    def unmark_applied(self, user_id: str, job_id: str) -> bool:
        """Returns True if removed, False if wasn't there."""
        ...


class FileAppliedStore:
    """File-backed AppliedStore with backwards-compat for legacy shape."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def is_applied(self, user_id: str, job_id: str) -> bool:
        return job_id in self._load(user_id)

    def list_applied(self, user_id: str) -> dict[str, ApplicationRecord]:
        return self._load(user_id)

    def get_application(
        self, user_id: str, job_id: str
    ) -> ApplicationRecord | None:
        return self._load(user_id).get(job_id)

    def mark_applied(
        self,
        user_id: str,
        job_id: str,
        *,
        resume_filename: str = "",
        resume_sha256: str = "",
        letter_version_used: int | None = None,
    ) -> bool:
        applications = self._load(user_id)
        was_new = job_id not in applications
        applications[job_id] = ApplicationRecord(
            applied_at=datetime.now(UTC),
            resume_filename=resume_filename,
            resume_sha256=resume_sha256,
            letter_version_used=letter_version_used,
        )
        self._save(user_id, applications)
        return was_new

    def unmark_applied(self, user_id: str, job_id: str) -> bool:
        applications = self._load(user_id)
        if job_id not in applications:
            return False
        del applications[job_id]
        self._save(user_id, applications)
        return True

    # ----- internals -----

    def _path(self, user_id: str) -> Path:
        return self.root / f"{user_id}.json"

    def _load(self, user_id: str) -> dict[str, ApplicationRecord]:
        path = self._path(user_id)
        if not path.exists():
            return {}
        data = json.loads(path.read_text())
        # Legacy shape: {"applied": ["id1", "id2"]} — fabricate empty
        # records so callers see the same dict-shaped result.
        if "applied" in data and "applications" not in data:
            return {
                job_id: ApplicationRecord() for job_id in data.get("applied", [])
            }
        applications_raw = data.get("applications", {})
        return {
            job_id: ApplicationRecord.model_validate(rec)
            for job_id, rec in applications_raw.items()
        }

    def _save(
        self, user_id: str, applications: dict[str, ApplicationRecord]
    ) -> None:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        # Sort keys for deterministic file content.
        payload = {
            "applications": {
                job_id: applications[job_id].model_dump(mode="json")
                for job_id in sorted(applications.keys())
            }
        }
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(path)
