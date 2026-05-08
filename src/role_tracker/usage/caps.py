"""Per-user daily-spend cap enforcement.

The cap is applied at the *route* layer just before any Anthropic /
OpenAI call. We reject the request with HTTP 429 if today's spend
plus the estimated cost of this call would exceed the configured cap.

The reset is implicit at midnight UTC because today's bucket in the
usage store is keyed by ISO date — at 00:00 UTC the next day's bucket
starts empty and previous days are no longer counted.

Two layers of cap config:

  1. Global default — `Settings.daily_cost_cap_usd` (env var
     `DAILY_COST_CAP_USD`). Applied to every user not overridden.

  2. Per-user override — `Settings.daily_cost_cap_usd_overrides` (env
     var `DAILY_COST_CAP_USD_OVERRIDES`), a JSON map of
     `{user_id: cap_usd}`. Used to give the admin (smrah) headroom
     for testing without raising the cap for friend testers. Empty
     map = global cap applies to everyone.

Why route-layer enforcement (not middleware): the feature name (and
therefore the per-call cost estimate) is only known inside the route.
The route already has a `usage_store` dependency, so adding one
function call is the minimal change that gets us the cap.
"""

from __future__ import annotations

import json
from typing import Protocol

from fastapi import HTTPException, status

from role_tracker.config import Settings
from role_tracker.usage.store import FEATURE_COST_USD


class _UsageStore(Protocol):
    def get_today_cost_usd(self, user_id: str) -> float: ...


def parse_cap_overrides(raw: str) -> dict[str, float]:
    """Parse the DAILY_COST_CAP_USD_OVERRIDES JSON env var.

    Empty string returns {}. Malformed JSON or non-numeric values
    raise ValueError so the failure is loud at startup rather than
    silently disabling the per-user override path.
    """
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(
            "DAILY_COST_CAP_USD_OVERRIDES must be a JSON object "
            "{user_id: cap_usd}"
        )
    out: dict[str, float] = {}
    for user_id, cap in parsed.items():
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("override keys must be non-empty user_ids")
        if not isinstance(cap, (int, float)):
            raise ValueError(
                f"override for {user_id!r} must be a number, got {type(cap).__name__}"
            )
        out[user_id] = float(cap)
    return out


def resolve_cap_usd(user_id: str, settings: Settings | None = None) -> float:
    """Resolve the daily cap for a specific user.

    Looks up `user_id` in the JSON overrides map; falls back to the
    global `daily_cost_cap_usd` setting if not present.
    """
    if settings is None:
        settings = Settings()
    overrides = parse_cap_overrides(settings.daily_cost_cap_usd_overrides)
    return overrides.get(user_id, settings.daily_cost_cap_usd)


def enforce_daily_cap(
    usage_store: _UsageStore,
    user_id: str,
    feature: str,
    cap_usd: float | None = None,
) -> None:
    """Raise HTTP 429 if user has hit today's cap.

    `cap_usd=None` (the default) resolves the cap from settings,
    respecting any per-user override. Pass an explicit `cap_usd` to
    short-circuit that resolution (useful in tests). A value of 0 or
    below disables the check entirely.
    """
    if cap_usd is None:
        cap_usd = resolve_cap_usd(user_id)
    if cap_usd <= 0:
        return
    spent = usage_store.get_today_cost_usd(user_id)
    add = FEATURE_COST_USD.get(feature, 0.0)
    if spent + add > cap_usd:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily cost cap reached (${spent:.2f} of ${cap_usd:.2f}). "
                f"Resets at 00:00 UTC."
            ),
        )
