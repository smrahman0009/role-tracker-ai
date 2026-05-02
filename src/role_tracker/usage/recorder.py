"""UsageRecorder — small (store, user_id) binding passed to call sites.

Each external-API client / agent step gets a recorder and calls one of:

    recorder.jsearch()            # one JSearch HTTP fetch
    recorder.feature("embedding") # any single Anthropic / OpenAI call

Two reasons for this thin wrapper instead of passing the UsageStore +
user_id pair through every layer:

  1. Call sites don't need to know about user_id plumbing.
  2. Tests can inject a NullRecorder and ignore usage entirely.

Recording is best-effort: if the store throws (disk full, race), we
swallow it — we'd rather drop a tick than fail the user's actual
request over a counter.
"""

from __future__ import annotations

from typing import Protocol


class UsageStoreLike(Protocol):
    def record_jsearch(self, user_id: str) -> None: ...
    def record_feature(self, user_id: str, feature: str) -> None: ...


class UsageRecorder:
    def __init__(self, store: UsageStoreLike, user_id: str) -> None:
        self._store = store
        self._user_id = user_id

    def jsearch(self) -> None:
        try:
            self._store.record_jsearch(self._user_id)
        except Exception:  # noqa: BLE001 - tracking is best-effort
            pass

    def feature(self, name: str) -> None:
        try:
            self._store.record_feature(self._user_id, name)
        except Exception:  # noqa: BLE001
            pass


class NullRecorder:
    """No-op recorder for tests and code paths without a user context."""

    def jsearch(self) -> None:
        pass

    def feature(self, name: str) -> None:
        pass
