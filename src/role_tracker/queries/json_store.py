"""JSON-file-backed query store.

Storage layout:
    data/queries/{user_id}.json
    {
      "version": 1,
      "queries": [
        {"query_id": "abc12345", "what": "data scientist", "where": "canada",
         "enabled": true, "created_at": "2026-04-28T..."}
      ]
    }

If the JSON file doesn't exist on first read, the store bootstraps from
`users/{user_id}.yaml` (where the CLI already keeps queries) so the
single-user CLI workflow keeps running unchanged.

Writes are atomic: serialize to a temp file, then rename. On a single-user
laptop or App Service F1 instance, this is sufficient — concurrent writes
aren't a concern at this scale.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

from role_tracker.queries.models import SavedQuery

DEFAULT_DATA_ROOT = Path("data/queries")
DEFAULT_BOOTSTRAP_ROOT = Path("users")


class JsonQueryStore:
    """Concrete QueryStore that persists to JSON on local disk."""

    def __init__(
        self,
        root: Path = DEFAULT_DATA_ROOT,
        bootstrap_yaml_root: Path = DEFAULT_BOOTSTRAP_ROOT,
    ) -> None:
        self.root = root
        self.bootstrap_yaml_root = bootstrap_yaml_root

    # ----- public API (matches QueryStore Protocol) -----

    def list_queries(self, user_id: str) -> list[SavedQuery]:
        return self._load(user_id)

    def get_query(self, user_id: str, query_id: str) -> SavedQuery | None:
        for q in self._load(user_id):
            if q.query_id == query_id:
                return q
        return None

    def add_query(self, user_id: str, what: str, where: str) -> SavedQuery:
        queries = self._load(user_id)
        new = SavedQuery(
            query_id=uuid.uuid4().hex[:8],
            what=what.strip(),
            where=where.strip(),
            enabled=True,
            created_at=datetime.now(UTC),
        )
        queries.append(new)
        self._save(user_id, queries)
        return new

    def update_query(
        self,
        user_id: str,
        query_id: str,
        *,
        what: str | None = None,
        where: str | None = None,
        enabled: bool | None = None,
    ) -> SavedQuery | None:
        queries = self._load(user_id)
        for i, q in enumerate(queries):
            if q.query_id != query_id:
                continue
            updated = q.model_copy(
                update={
                    k: v
                    for k, v in {
                        "what": what.strip() if what is not None else None,
                        "where": where.strip() if where is not None else None,
                        "enabled": enabled,
                    }.items()
                    if v is not None
                }
            )
            queries[i] = updated
            self._save(user_id, queries)
            return updated
        return None

    def delete_query(self, user_id: str, query_id: str) -> bool:
        queries = self._load(user_id)
        before = len(queries)
        queries = [q for q in queries if q.query_id != query_id]
        if len(queries) == before:
            return False
        self._save(user_id, queries)
        return True

    # ----- internals -----

    def _path(self, user_id: str) -> Path:
        return self.root / f"{user_id}.json"

    def _load(self, user_id: str) -> list[SavedQuery]:
        path = self._path(user_id)
        if path.exists():
            data = json.loads(path.read_text())
            return [SavedQuery(**q) for q in data.get("queries", [])]
        # First read: bootstrap from YAML if present, otherwise empty list.
        bootstrapped = self._bootstrap_from_yaml(user_id)
        if bootstrapped:
            self._save(user_id, bootstrapped)
        return bootstrapped

    def _save(self, user_id: str, queries: list[SavedQuery]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(user_id)
        # Atomic write: temp file, then rename.
        tmp = path.with_suffix(".json.tmp")
        payload = {
            "version": 1,
            "queries": [q.model_dump(mode="json") for q in queries],
        }
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(path)

    def _bootstrap_from_yaml(self, user_id: str) -> list[SavedQuery]:
        yaml_path = self.bootstrap_yaml_root / f"{user_id}.yaml"
        if not yaml_path.exists():
            return []
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        raw = data.get("queries") or []
        now = datetime.now(UTC)
        return [
            SavedQuery(
                query_id=uuid.uuid4().hex[:8],
                what=q.get("what", ""),
                where=q.get("where", "canada"),
                enabled=True,
                created_at=now,
            )
            for q in raw
            if q.get("what")
        ]
