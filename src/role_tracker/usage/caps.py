"""Per-user daily-spend cap enforcement.

The cap is applied at the *route* layer just before any Anthropic /
OpenAI call. We reject the request with HTTP 429 if today's spend
plus the estimated cost of this call would exceed the configured cap.

The reset is implicit at midnight UTC because today's bucket in the
usage store is keyed by ISO date — at 00:00 UTC the next day's bucket
starts empty and previous days are no longer counted.

Why route-layer enforcement (not middleware): the feature name (and
therefore the per-call cost estimate) is only known inside the route.
The route already has a `usage_store` dependency, so adding one
function call is the minimal change that gets us the cap.
"""

from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException, status

from role_tracker.config import Settings
from role_tracker.usage.store import FEATURE_COST_USD


class _UsageStore(Protocol):
    def get_today_cost_usd(self, user_id: str) -> float: ...


def enforce_daily_cap(
    usage_store: _UsageStore,
    user_id: str,
    feature: str,
    cap_usd: float | None = None,
) -> None:
    """Raise HTTP 429 if user has hit today's cap.

    `cap_usd` defaults to `Settings().daily_cost_cap_usd`. A value of
    0 (or below) disables the check entirely — used in dev and in
    tests that don't want to mock today's spend.
    """
    if cap_usd is None:
        cap_usd = Settings().daily_cost_cap_usd
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
