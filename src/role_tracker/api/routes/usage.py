"""Usage endpoints — surface per-user, per-month rollups for the
Usage / Quota page.

GET /users/{user_id}/usage
    Current month (always present, even if zero) + up to 5 prior months.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from role_tracker.api.routes.jobs import get_usage_store
from role_tracker.api.schemas import (
    FeatureCount,
    UsageMonth,
    UsageResponse,
)
from role_tracker.usage import (
    ANTHROPIC_FEATURES,
    FEATURE_COST_USD,
    OPENAI_FEATURES,
    MonthlyUsage,
    UsageStore,
)

router = APIRouter(prefix="/users/{user_id}", tags=["usage"])


def _current_year_month() -> str:
    now = datetime.now(UTC)
    return f"{now.year:04d}-{now.month:02d}"


def _to_response(month: MonthlyUsage) -> UsageMonth:
    """Flatten the stored model into a UI-friendly shape, with features
    sorted by provider then descending cost so Anthropic features lead."""
    feature_counts = []
    for feature, count in month.feature_calls.items():
        cost = FEATURE_COST_USD.get(feature, 0.0) * count
        feature_counts.append(
            FeatureCount(
                feature=feature, count=count, estimated_cost_usd=cost
            )
        )

    def sort_key(fc: FeatureCount) -> tuple[int, float]:
        # Anthropic first (0), then OpenAI (1), then unknown (2);
        # within group, higher cost first.
        if fc.feature in ANTHROPIC_FEATURES:
            bucket = 0
        elif fc.feature in OPENAI_FEATURES:
            bucket = 1
        else:
            bucket = 2
        return (bucket, -fc.estimated_cost_usd)

    feature_counts.sort(key=sort_key)
    return UsageMonth(
        year_month=month.year_month,
        jsearch_calls=month.jsearch_calls,
        feature_calls=feature_counts,
        estimated_anthropic_cost_usd=month.estimated_anthropic_cost_usd,
        estimated_openai_cost_usd=month.estimated_openai_cost_usd,
        estimated_total_cost_usd=month.estimated_total_cost_usd,
    )


@router.get("/usage", response_model=UsageResponse)
def get_usage(
    user_id: str,
    usage_store: UsageStore = Depends(get_usage_store),
) -> UsageResponse:
    """Return the current month's rollup + up to 5 prior months."""
    ym = _current_year_month()
    current = usage_store.get_month(user_id, ym)
    months = usage_store.list_months(user_id)
    history = [m for m in months if m.year_month != ym][:5]
    return UsageResponse(
        current=_to_response(current),
        history=[_to_response(m) for m in history],
    )
