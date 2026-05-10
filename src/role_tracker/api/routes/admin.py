"""Admin-only endpoints — currently just the global hidden-publishers list.

Auth model: every request goes through BearerTokenMiddleware, which
binds the token to a user_id and stashes it on request.state. The
require_admin dependency below loads that user's profile and rejects
with 403 unless `is_admin` is true.

Non-admin users can still GET the global list — the ranking pipeline
needs to read it during job-snapshot building. PUT is admin-only.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from role_tracker.global_settings.base import GlobalSettingsStore
from role_tracker.global_settings.factory import make_global_settings_store
from role_tracker.global_settings.models import GlobalHiddenPublishers
from role_tracker.users.base import UserProfileStore
from role_tracker.users.factory import make_user_profile_store

router = APIRouter()


# ----- Dependencies ----------------------------------------------------


def get_global_settings_store() -> GlobalSettingsStore:
    return make_global_settings_store()


def get_profile_store() -> UserProfileStore:
    # Mirrors api/routes/profile.py.get_profile_store; duplicated to
    # avoid a cross-route import. If a third route ever needs this,
    # promote to a shared dependencies module.
    return make_user_profile_store()


def require_admin(
    request: Request,
    profile_store: UserProfileStore = Depends(get_profile_store),
) -> str:
    """Require that the calling user has is_admin=True. Returns user_id.

    In dev mode (BearerTokenMiddleware bypassed because no APP_TOKEN /
    user-token map is configured), request.state.user_id is unset.
    To keep local development frictionless we treat that case as
    "admin-allowed" — there's no auth at all in dev. In production
    the middleware always sets it.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        # Dev bypass — no auth configured at all.
        return ""
    try:
        profile = profile_store.get_user(user_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        ) from exc
    if not profile.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user_id


# ----- Schemas ---------------------------------------------------------


class HiddenPublishersResponse(BaseModel):
    publishers: list[str]
    updated_at: datetime
    updated_by: str


class UpdateHiddenPublishersRequest(BaseModel):
    items: list[str] = Field(default_factory=list)


# ----- Routes ----------------------------------------------------------


@router.get(
    "/global/hidden-publishers",
    response_model=HiddenPublishersResponse,
)
def get_global_hidden_publishers(
    store: GlobalSettingsStore = Depends(get_global_settings_store),
) -> HiddenPublishersResponse:
    """Return the global hidden-publishers list.

    Any authenticated user may read it — the ranking pipeline needs
    it to filter snapshots, and surfacing a read-only view to non-
    admin UIs is allowed (today the frontend only shows it to admins
    but that's a UX choice, not a security boundary).
    """
    value = store.get_hidden_publishers()
    return HiddenPublishersResponse(
        publishers=value.publishers,
        updated_at=value.updated_at,
        updated_by=value.updated_by,
    )


@router.put(
    "/global/hidden-publishers",
    response_model=HiddenPublishersResponse,
)
def update_global_hidden_publishers(
    body: UpdateHiddenPublishersRequest,
    user_id: str = Depends(require_admin),
    store: GlobalSettingsStore = Depends(get_global_settings_store),
) -> HiddenPublishersResponse:
    """Replace the global hidden-publishers list. Admin only."""
    cleaned = _clean_items(body.items)
    value = GlobalHiddenPublishers(
        publishers=cleaned,
        updated_at=datetime.now(UTC),
        updated_by=user_id or "dev",
    )
    store.set_hidden_publishers(value)
    return HiddenPublishersResponse(
        publishers=value.publishers,
        updated_at=value.updated_at,
        updated_by=value.updated_by,
    )


# ----- Helpers ---------------------------------------------------------


def _clean_items(items: list[str]) -> list[str]:
    """Strip whitespace, drop empties, dedupe case-insensitively while
    preserving the first-seen casing.

    Mirrors the same logic in api/routes/profile.py for the per-user
    hidden lists so admins get the same UX as users do for their
    own filters.
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        cleaned = raw.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out
