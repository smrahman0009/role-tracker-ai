"""Storage protocol for cross-tenant admin-managed settings."""

from __future__ import annotations

from typing import Protocol

from role_tracker.global_settings.models import GlobalHiddenPublishers


class GlobalSettingsStore(Protocol):
    """Persistence for admin-managed cross-tenant settings.

    Today there's a single document (hidden_publishers). The
    interface is keyed by document name so additional admin knobs
    can slot in without growing the protocol.
    """

    def get_hidden_publishers(self) -> GlobalHiddenPublishers:
        """Return the current global hidden-publishers list.

        Returns an empty GlobalHiddenPublishers when the document
        has never been written — callers should treat that as the
        valid "nothing blocked yet" state, not an error.
        """
        ...

    def set_hidden_publishers(self, value: GlobalHiddenPublishers) -> None:
        """Persist the global hidden-publishers list (overwrite)."""
        ...
