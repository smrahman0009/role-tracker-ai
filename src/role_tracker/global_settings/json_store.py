"""JSON-file-backed GlobalSettingsStore for local dev.

Writes a single file per document under ./data/global/. Mirrors the
on-disk layout used by the other file-backed stores so a developer
can `cat data/global/hidden_publishers.json` to inspect / hand-edit
during testing.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from role_tracker.global_settings.models import GlobalHiddenPublishers


class JsonGlobalSettingsStore:
    """File-backed implementation of GlobalSettingsStore."""

    def __init__(self, base_dir: Path | str = "data/global") -> None:
        self._base_dir = Path(base_dir)

    # ----- Reads -------------------------------------------------------

    def get_hidden_publishers(self) -> GlobalHiddenPublishers:
        path = self._publishers_path()
        if not path.exists():
            return GlobalHiddenPublishers()
        return GlobalHiddenPublishers.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    # ----- Writes ------------------------------------------------------

    def set_hidden_publishers(self, value: GlobalHiddenPublishers) -> None:
        path = self._publishers_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write — write to a tempfile in the same directory, then
        # rename. Avoids partial files on Ctrl-C between open and close.
        payload = value.model_dump_json(indent=2)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)

    # ----- Helpers -----------------------------------------------------

    def _publishers_path(self) -> Path:
        return self._base_dir / "hidden_publishers.json"
