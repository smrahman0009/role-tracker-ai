"""Data shapes for global (admin-managed) settings."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GlobalHiddenPublishers(BaseModel):
    """Cross-tenant block-list applied to every user's job snapshots.

    The list is editable only by admin users (UserProfile.is_admin).
    Non-admin users never see this in their UI; the ranking pipeline
    just unions it into the per-user filters before scoring.
    """

    publishers: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=_now)
    updated_by: str = ""
