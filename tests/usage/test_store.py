"""Tests for FileUsageStore — record + read + retention."""

from pathlib import Path

import pytest

from role_tracker.usage import FileUsageStore, MonthlyUsage
from role_tracker.usage.recorder import NullRecorder, UsageRecorder
from role_tracker.usage.store import KEEP_MONTHS


@pytest.fixture
def store(tmp_path: Path) -> FileUsageStore:
    return FileUsageStore(root=tmp_path / "usage")


def test_record_jsearch_increments_current_month(store: FileUsageStore) -> None:
    store.record_jsearch("alice")
    store.record_jsearch("alice")
    months = store.list_months("alice")
    assert len(months) == 1
    assert months[0].jsearch_calls == 2


def test_record_feature_per_user_isolation(store: FileUsageStore) -> None:
    store.record_feature("alice", "embedding")
    store.record_feature("bob", "cover_letter_polish")
    [a] = store.list_months("alice")
    [b] = store.list_months("bob")
    assert a.feature_calls == {"embedding": 1}
    assert b.feature_calls == {"cover_letter_polish": 1}


def test_estimated_costs_sum_correctly(store: FileUsageStore) -> None:
    # 2 generates ($0.05) + 4 embeddings ($0.0005) + 1 polish ($0.005)
    for _ in range(2):
        store.record_feature("alice", "cover_letter_generate")
    for _ in range(4):
        store.record_feature("alice", "embedding")
    store.record_feature("alice", "cover_letter_polish")

    [m] = store.list_months("alice")
    assert m.estimated_anthropic_cost_usd == pytest.approx(0.105)
    assert m.estimated_openai_cost_usd == pytest.approx(0.002)
    assert m.estimated_total_cost_usd == pytest.approx(0.107)


def test_get_month_returns_zero_record_when_missing(
    store: FileUsageStore,
) -> None:
    m = store.get_month("alice", "1999-01")
    assert isinstance(m, MonthlyUsage)
    assert m.jsearch_calls == 0
    assert m.feature_calls == {}


def test_retention_caps_at_keep_months(
    tmp_path: Path, store: FileUsageStore
) -> None:
    """When >KEEP_MONTHS rollups exist on disk, _save trims to the
    most recent KEEP_MONTHS."""
    # Hand-craft a file with KEEP_MONTHS+2 months, then trigger a save.
    months = {
        f"2025-{i:02d}": MonthlyUsage(year_month=f"2025-{i:02d}", jsearch_calls=i)
        for i in range(1, KEEP_MONTHS + 3)
    }
    store._save("alice", months)  # noqa: SLF001 — internal helper

    persisted = store.list_months("alice")
    assert len(persisted) == KEEP_MONTHS
    # Newest first; the months pruned should be the lowest-numbered.
    kept_ids = {m.year_month for m in persisted}
    assert "2025-01" not in kept_ids
    assert "2025-02" not in kept_ids


def test_recorder_swallows_store_errors() -> None:
    """UsageRecorder.feature must not raise — best-effort tracking."""

    class Boom:
        def record_jsearch(self, user_id: str) -> None:
            raise RuntimeError("disk full")

        def record_feature(self, user_id: str, feature: str) -> None:
            raise RuntimeError("disk full")

    rec = UsageRecorder(Boom(), "alice")
    rec.jsearch()  # must not raise
    rec.feature("embedding")  # must not raise


def test_null_recorder_is_noop() -> None:
    rec = NullRecorder()
    rec.jsearch()
    rec.feature("anything")
