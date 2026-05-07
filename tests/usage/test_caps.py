"""Tests for the per-user daily-spend cap."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from role_tracker.usage import FileUsageStore
from role_tracker.usage.caps import enforce_daily_cap


@pytest.fixture
def store(tmp_path: Path) -> FileUsageStore:
    return FileUsageStore(root=tmp_path / "usage")


def test_under_cap_does_not_raise(store: FileUsageStore) -> None:
    enforce_daily_cap(store, "alice", "cover_letter_draft", cap_usd=1.50)


def test_zero_cap_disables_check(store: FileUsageStore) -> None:
    # Even with a huge spent amount, cap=0 is a bypass.
    for _ in range(10000):
        store.record_feature("alice", "cover_letter_draft")
    enforce_daily_cap(store, "alice", "cover_letter_draft", cap_usd=0)


def test_exceeding_cap_raises_429(store: FileUsageStore) -> None:
    # 80 drafts × $0.020 = $1.60 > $1.50.
    for _ in range(80):
        store.record_feature("alice", "cover_letter_draft")
    with pytest.raises(HTTPException) as exc_info:
        enforce_daily_cap(store, "alice", "cover_letter_draft", cap_usd=1.50)
    assert exc_info.value.status_code == 429
    assert "00:00 utc" in exc_info.value.detail.lower()


def test_cap_per_user(store: FileUsageStore) -> None:
    """Alice burning her cap doesn't affect Bob."""
    for _ in range(80):
        store.record_feature("alice", "cover_letter_draft")
    # Alice over → 429.
    with pytest.raises(HTTPException):
        enforce_daily_cap(store, "alice", "cover_letter_draft", cap_usd=1.50)
    # Bob still under → no raise.
    enforce_daily_cap(store, "bob", "cover_letter_draft", cap_usd=1.50)


def test_today_cost_resets_across_iso_days(
    store: FileUsageStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Today's bucket only counts today; yesterday's calls don't."""
    import role_tracker.usage.store as store_mod

    # Pretend yesterday: monkeypatch _today_iso to a fixed past date.
    monkeypatch.setattr(store_mod, "_today_iso", lambda: "2026-05-06")
    for _ in range(80):
        store.record_feature("alice", "cover_letter_draft")
    yesterday_cost = store.get_today_cost_usd("alice")
    assert yesterday_cost == pytest.approx(80 * 0.020)

    # Roll over to today. Yesterday's calls don't count toward today.
    monkeypatch.setattr(store_mod, "_today_iso", lambda: "2026-05-07")
    today_cost = store.get_today_cost_usd("alice")
    assert today_cost == 0.0
    # Cap check passes again.
    enforce_daily_cap(store, "alice", "cover_letter_draft", cap_usd=1.50)


def test_get_today_cost_zero_for_unknown_user(store: FileUsageStore) -> None:
    assert store.get_today_cost_usd("nobody") == 0.0
