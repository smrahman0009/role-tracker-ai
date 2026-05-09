"""UsageStore — per-user, per-month rollups of external-API usage.

We track three kinds of events:

  - JSearch fetches            (count requests; the user's RapidAPI plan
                                has a hard monthly cap)
  - OpenAI embeddings          (count requests; cost ≈ $0.001 each)
  - Anthropic feature calls    (one event per cover-letter / refine /
                                polish / why-interested / url-extract;
                                cost estimated via per-feature averages)

Storage layout (per user JSON file):

    data/usage/{user_id}.json
    {
      "months": {
        "2026-05": {
          "year_month": "2026-05",
          "jsearch_calls": 47,
          "feature_calls": {
            "embedding": 12,
            "cover_letter_generate": 3,
            "cover_letter_polish": 8,
            ...
          }
        },
        "2026-04": { ... }
      }
    }

Why per-feature counts instead of token-accurate costs: instrumenting
every Anthropic call site to extract `response.usage` is invasive and
tokens-per-feature don't vary much in practice. Per-feature averages
give a usable budget-tracking signal with zero per-call plumbing.
Real costs live on the Anthropic / OpenAI dashboards; we label our
numbers as "Estimated".

Phase 7 deploy: swap FileUsageStore → CosmosUsageStore; route deps
unchanged.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

DEFAULT_ROOT = Path("data/usage")
KEEP_MONTHS = 6


# ----- Per-feature cost estimates (USD per call) -----
#
# Round numbers chosen to match observed average token usage at current
# Anthropic / OpenAI rates (May 2026). Recurring re-tune as the agent
# evolves; a slight over-estimate is fine since the dashboard labels
# everything "Estimated".

FEATURE_COST_USD: dict[str, float] = {
    # OpenAI text-embedding-3-small — typical job description ~500 tokens
    # per embedding call, $0.02/M tokens, batched ~50 jobs per call.
    "embedding": 0.0005,
    # Cover-letter agent loop — Sonnet generation + Haiku critique +
    # cache reads. ~$0.05 typical, ~$0.07 worst case.
    "cover_letter_generate": 0.05,
    # Refine — single Sonnet call against a smaller prompt.
    "cover_letter_refine": 0.025,
    # Cover-letter polish — single Haiku call (3-second grammar pass).
    "cover_letter_polish": 0.005,
    # Why-interested polish — single Haiku call cleaning grammar in
    # text the user typed themselves. The "generate full motivation
    # answer" capability was removed in May 2026; see HANDBOOK.md.
    "why_interested_polish": 0.005,
    # URL-extract LLM refine — single Haiku call against the JD body.
    "url_extract_llm_refine": 0.005,
    # JD summary panel. Sonnet by default, ~80-120 tokens out.
    "cover_letter_summary": 0.020,
    # Cover-letter generate with extended thinking enabled. Same agent
    # loop as cover_letter_generate but with Anthropic's extended
    # thinking budget; thinking tokens push the per-call cost up.
    "cover_letter_generate_extended": 0.12,
}


# ----- Provider categorisation -----
#
# Each feature gets bucketed into a provider for the UI cards. JSearch
# is its own counter (jsearch_calls) so it's not in this map.

ANTHROPIC_FEATURES = {
    "cover_letter_generate",
    "cover_letter_generate_extended",
    "cover_letter_refine",
    "cover_letter_polish",
    "cover_letter_summary",
    "why_interested_polish",
    "url_extract_llm_refine",
}
OPENAI_FEATURES = {"embedding"}


class MonthlyUsage(BaseModel):
    """One month's rollup. All counters default to 0."""

    year_month: str  # "YYYY-MM"

    # JSearch — count of fetch_jobs HTTP calls. Each call burns 1
    # request from the user's RapidAPI plan (note: num_pages may
    # multiply real cost on some plans; we only track the call count
    # as the simplest visible-quota signal).
    jsearch_calls: int = 0

    # Per-feature counters. Keys are stable strings — see FEATURE_COST_USD.
    feature_calls: dict[str, int] = Field(default_factory=dict)

    # Per-day, per-feature counts. Outer key: ISO date "YYYY-MM-DD".
    # Inner key: feature name. Used for the per-user $/day cap (MU-2);
    # resets implicitly at midnight UTC because today's bucket is
    # only populated when today's calls happen.
    daily_feature_calls: dict[str, dict[str, int]] = Field(default_factory=dict)

    # ----- Derived fields -----

    @property
    def estimated_anthropic_cost_usd(self) -> float:
        return sum(
            FEATURE_COST_USD.get(feat, 0.0) * count
            for feat, count in self.feature_calls.items()
            if feat in ANTHROPIC_FEATURES
        )

    @property
    def estimated_openai_cost_usd(self) -> float:
        return sum(
            FEATURE_COST_USD.get(feat, 0.0) * count
            for feat, count in self.feature_calls.items()
            if feat in OPENAI_FEATURES
        )

    @property
    def estimated_total_cost_usd(self) -> float:
        return self.estimated_anthropic_cost_usd + self.estimated_openai_cost_usd


class UsageStore(Protocol):
    def get_month(self, user_id: str, year_month: str) -> MonthlyUsage: ...
    def list_months(self, user_id: str) -> list[MonthlyUsage]: ...
    def record_jsearch(self, user_id: str) -> None: ...
    def record_feature(self, user_id: str, feature: str) -> None: ...
    def get_today_cost_usd(self, user_id: str) -> float: ...


def _today_iso() -> str:
    now = datetime.now(UTC)
    return f"{now.year:04d}-{now.month:02d}-{now.day:02d}"


def cost_of_features(features: dict[str, int]) -> float:
    """Sum FEATURE_COST_USD * count over a {feature: count} map."""
    return sum(FEATURE_COST_USD.get(f, 0.0) * c for f, c in features.items())


class FileUsageStore:
    """JSON-file-backed UsageStore. Per-user file, monthly rollups."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def get_month(self, user_id: str, year_month: str) -> MonthlyUsage:
        months = self._load(user_id)
        return months.get(year_month) or MonthlyUsage(year_month=year_month)

    def list_months(self, user_id: str) -> list[MonthlyUsage]:
        months = self._load(user_id)
        return sorted(months.values(), key=lambda m: m.year_month, reverse=True)

    def record_jsearch(self, user_id: str) -> None:
        with self._mutate(user_id) as month:
            month.jsearch_calls += 1

    def record_feature(self, user_id: str, feature: str) -> None:
        with self._mutate(user_id) as month:
            month.feature_calls[feature] = (
                month.feature_calls.get(feature, 0) + 1
            )
            today = _today_iso()
            day_bucket = month.daily_feature_calls.setdefault(today, {})
            day_bucket[feature] = day_bucket.get(feature, 0) + 1

    def get_today_cost_usd(self, user_id: str) -> float:
        ym = _current_year_month()
        month = self.get_month(user_id, ym)
        today = _today_iso()
        return cost_of_features(month.daily_feature_calls.get(today, {}))

    # ----- internals -----

    def _path(self, user_id: str) -> Path:
        return self.root / f"{user_id}.json"

    def _load(self, user_id: str) -> dict[str, MonthlyUsage]:
        path = self._path(user_id)
        if not path.exists():
            return {}
        data = json.loads(path.read_text())
        months_raw = data.get("months") or {}
        return {
            ym: MonthlyUsage.model_validate(rec)
            for ym, rec in months_raw.items()
        }

    def _save(self, user_id: str, months: dict[str, MonthlyUsage]) -> None:
        if len(months) > KEEP_MONTHS:
            kept = sorted(months.keys(), reverse=True)[:KEEP_MONTHS]
            months = {k: months[k] for k in kept}
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        payload = {
            "months": {
                ym: months[ym].model_dump(mode="json")
                for ym in sorted(months.keys())
            }
        }
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(path)

    def _mutate(self, user_id: str) -> _MutateContext:
        return _MutateContext(self, user_id)


def _current_year_month() -> str:
    now = datetime.now(UTC)
    return f"{now.year:04d}-{now.month:02d}"


class _MutateContext:
    """Read-modify-write helper used by the record_* methods."""

    def __init__(self, store: FileUsageStore, user_id: str) -> None:
        self._store = store
        self._user_id = user_id
        self._months: dict[str, MonthlyUsage] = {}
        self._ym = _current_year_month()

    def __enter__(self) -> MonthlyUsage:
        self._months = self._store._load(self._user_id)
        if self._ym not in self._months:
            self._months[self._ym] = MonthlyUsage(year_month=self._ym)
        return self._months[self._ym]

    def __exit__(self, *_exc: object) -> None:
        self._store._save(self._user_id, self._months)
