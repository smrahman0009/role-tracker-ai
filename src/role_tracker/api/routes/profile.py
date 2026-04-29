"""Profile + Hidden Lists endpoints — see docs/api_spec.md §7 + §8.

Both endpoint groups read and write to the user's UserProfile YAML
file. They share a YAML-store dependency so a test can override once
and affect both routers.

UI labels these as "Hidden …" lists; the API field names use the
historical `exclude_*` for stable backward compatibility (per the
convention in api_spec.md).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status

from role_tracker.api.schemas import (
    HiddenListsResponse,
    ProfileResponse,
    UpdateHiddenListRequest,
    UpdateProfileRequest,
)
from role_tracker.users.base import UserProfileStore
from role_tracker.users.yaml_store import YamlUserProfileStore

router = APIRouter(tags=["profile"])


def get_profile_store() -> UserProfileStore:
    """Tests override this with a tmp-rooted YAML store or a stub."""
    return YamlUserProfileStore()


# ============================================================
# §7. PROFILE
# ============================================================


@router.get(
    "/users/{user_id}/profile",
    response_model=ProfileResponse,
)
def get_profile(
    user_id: str,
    store: UserProfileStore = Depends(get_profile_store),
) -> ProfileResponse:
    """Return contact info + per-field show-in-letter flags."""
    profile = _load_or_404(store, user_id)
    return ProfileResponse(
        name=profile.name,
        phone=profile.phone,
        email=profile.email,
        city=profile.city,
        linkedin_url=profile.linkedin_url,
        github_url=profile.github_url,
        portfolio_url=profile.portfolio_url,
        show_phone_in_header=profile.show_phone_in_header,
        show_email_in_header=profile.show_email_in_header,
        show_city_in_header=profile.show_city_in_header,
        show_linkedin_in_header=profile.show_linkedin_in_header,
        show_github_in_header=profile.show_github_in_header,
        show_portfolio_in_header=profile.show_portfolio_in_header,
    )


@router.put(
    "/users/{user_id}/profile",
    response_model=ProfileResponse,
)
def update_profile(
    user_id: str,
    body: UpdateProfileRequest,
    store: UserProfileStore = Depends(get_profile_store),
) -> ProfileResponse:
    """Patch any subset of contact fields and/or show-in-letter flags."""
    profile = _load_or_404(store, user_id)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = profile.model_copy(update=updates)
    store.save_user(updated)
    return get_profile(user_id, store=store)


# ============================================================
# §8. HIDDEN LISTS (companies / title keywords / publishers)
# ============================================================


HiddenKind = Literal["companies", "title-keywords", "publishers"]


@router.get(
    "/users/{user_id}/hidden",
    response_model=HiddenListsResponse,
)
def get_hidden_lists(
    user_id: str,
    store: UserProfileStore = Depends(get_profile_store),
) -> HiddenListsResponse:
    """Return all three hidden lists in one response."""
    profile = _load_or_404(store, user_id)
    return HiddenListsResponse(
        companies=profile.exclude_companies,
        title_keywords=profile.exclude_title_keywords,
        publishers=profile.exclude_publishers,
    )


@router.put(
    "/users/{user_id}/hidden/companies",
    response_model=list[str],
)
def update_hidden_companies(
    user_id: str,
    body: UpdateHiddenListRequest,
    store: UserProfileStore = Depends(get_profile_store),
) -> list[str]:
    """Replace the entire companies list. Send {"items": []} to clear all."""
    profile = _load_or_404(store, user_id)
    cleaned = _clean_items(body.items)
    updated = profile.model_copy(update={"exclude_companies": cleaned})
    store.save_user(updated)
    return cleaned


@router.put(
    "/users/{user_id}/hidden/title-keywords",
    response_model=list[str],
)
def update_hidden_title_keywords(
    user_id: str,
    body: UpdateHiddenListRequest,
    store: UserProfileStore = Depends(get_profile_store),
) -> list[str]:
    """Replace the entire title-keywords list."""
    profile = _load_or_404(store, user_id)
    cleaned = _clean_items(body.items)
    updated = profile.model_copy(update={"exclude_title_keywords": cleaned})
    store.save_user(updated)
    return cleaned


@router.put(
    "/users/{user_id}/hidden/publishers",
    response_model=list[str],
)
def update_hidden_publishers(
    user_id: str,
    body: UpdateHiddenListRequest,
    store: UserProfileStore = Depends(get_profile_store),
) -> list[str]:
    """Replace the entire publishers list."""
    profile = _load_or_404(store, user_id)
    cleaned = _clean_items(body.items)
    updated = profile.model_copy(update={"exclude_publishers": cleaned})
    store.save_user(updated)
    return cleaned


# ----- Helpers -----


def _load_or_404(store: UserProfileStore, user_id: str):  # type: ignore[no-untyped-def]
    try:
        return store.get_user(user_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User profile '{user_id}' not found",
        ) from exc


def _clean_items(items: list[str]) -> list[str]:
    """Strip whitespace, drop empties, dedupe while preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        s = raw.strip()
        if not s or s.lower() in seen:
            continue
        seen.add(s.lower())
        out.append(s)
    return out
