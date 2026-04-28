"""Resume storage — Protocol + file-backed implementation.

Storage layout (matches the CLI's existing layout so both can co-exist):
    data/resumes/{user_id}.pdf            — the PDF itself
    data/resumes/{user_id}.meta.json      — original-filename + uploaded_at

Size and SHA-256 are computed on demand from the file contents — no need
to keep them in the meta file. If a PDF exists without a meta file (e.g.
because the user dropped one in by hand for the CLI), the store returns
sensible defaults so the API still works.

Phase 8 deploy: we'll add BlobResumeStore that reads/writes Azure Blob
Storage. Routes don't change — they depend on the Protocol, not the
concrete class.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from role_tracker.resume.models import ResumeMetadata

DEFAULT_DATA_ROOT = Path("data/resumes")


class ResumeStore(Protocol):
    """Abstract storage for a single resume per user."""

    def get_metadata(self, user_id: str) -> ResumeMetadata | None: ...
    def get_file_bytes(self, user_id: str) -> bytes | None: ...
    def save_resume(
        self, user_id: str, *, content: bytes, filename: str
    ) -> ResumeMetadata: ...


class FileResumeStore:
    """ResumeStore implementation that persists to local disk."""

    def __init__(self, root: Path = DEFAULT_DATA_ROOT) -> None:
        self.root = root

    # ----- public API (matches ResumeStore Protocol) -----

    def get_metadata(self, user_id: str) -> ResumeMetadata | None:
        pdf_path = self._pdf_path(user_id)
        if not pdf_path.exists():
            return None
        # Load original filename + uploaded_at from meta file if present;
        # fall back to file system info otherwise.
        meta_path = self._meta_path(user_id)
        original_filename = f"{user_id}.pdf"
        uploaded_at = datetime.fromtimestamp(pdf_path.stat().st_mtime, tz=UTC)
        if meta_path.exists():
            data = json.loads(meta_path.read_text())
            original_filename = data.get("filename", original_filename)
            if "uploaded_at" in data:
                uploaded_at = datetime.fromisoformat(data["uploaded_at"])
        return ResumeMetadata(
            filename=original_filename,
            size_bytes=pdf_path.stat().st_size,
            uploaded_at=uploaded_at,
            sha256=self._hash(pdf_path),
        )

    def get_file_bytes(self, user_id: str) -> bytes | None:
        path = self._pdf_path(user_id)
        return path.read_bytes() if path.exists() else None

    def get_file_path(self, user_id: str) -> Path | None:
        """File-store-specific helper. Used by the matching pipeline which
        needs a Path for pypdf. Not part of the Protocol — backends like
        Blob would have to download to a temp path."""
        path = self._pdf_path(user_id)
        return path if path.exists() else None

    def save_resume(
        self, user_id: str, *, content: bytes, filename: str
    ) -> ResumeMetadata:
        self.root.mkdir(parents=True, exist_ok=True)
        pdf_path = self._pdf_path(user_id)
        meta_path = self._meta_path(user_id)
        now = datetime.now(UTC)

        # Atomic write of the PDF.
        tmp = pdf_path.with_suffix(".pdf.tmp")
        tmp.write_bytes(content)
        tmp.replace(pdf_path)

        # Persist original filename + uploaded_at.
        meta_path.write_text(
            json.dumps(
                {
                    "filename": filename,
                    "uploaded_at": now.isoformat(),
                },
                indent=2,
            )
            + "\n"
        )

        return ResumeMetadata(
            filename=filename,
            size_bytes=len(content),
            uploaded_at=now,
            sha256=hashlib.sha256(content).hexdigest(),
        )

    # ----- internals -----

    def _pdf_path(self, user_id: str) -> Path:
        return self.root / f"{user_id}.pdf"

    def _meta_path(self, user_id: str) -> Path:
        return self.root / f"{user_id}.meta.json"

    @staticmethod
    def _hash(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
