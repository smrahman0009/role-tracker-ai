"""Tests for DynamoDBLetterStore — same Protocol as FileLetterStore."""

import pytest

from role_tracker.aws.dynamodb_letter_store import DynamoDBLetterStore
from tests.aws.conftest import make_table

TABLE_NAME = "role-tracker-letters"
SK = "job_version"


@pytest.fixture
def store(dynamodb_resource: object) -> DynamoDBLetterStore:
    make_table(dynamodb_resource, TABLE_NAME, SK)
    return DynamoDBLetterStore(
        TABLE_NAME, dynamodb_resource=dynamodb_resource
    )


def _save_basic(store: DynamoDBLetterStore, **overrides: object) -> object:
    kwargs = dict(
        text="Dear hiring manager, I am excited.",
        strategy={"primary_project": "X"},
        critique={"verdict": "approved"},
    )
    kwargs.update(overrides)
    return store.save_letter("alice", "j1", **kwargs)  # type: ignore[arg-type]


def test_save_assigns_version_one_on_first_save(
    store: DynamoDBLetterStore,
) -> None:
    letter = _save_basic(store)
    assert letter.version == 1


def test_save_increments_version_per_job(
    store: DynamoDBLetterStore,
) -> None:
    a = _save_basic(store)
    b = _save_basic(store)
    c = _save_basic(store)
    assert [a.version, b.version, c.version] == [1, 2, 3]


def test_per_job_isolation(store: DynamoDBLetterStore) -> None:
    """Versions are scoped to (user, job) — saving for j2 starts at 1."""
    store.save_letter(
        "alice", "j1", text="a", strategy=None, critique=None
    )
    j2 = store.save_letter(
        "alice", "j2", text="b", strategy=None, critique=None
    )
    assert j2.version == 1


def test_list_versions_returns_all_versions(
    store: DynamoDBLetterStore,
) -> None:
    _save_basic(store)
    _save_basic(store)
    _save_basic(store)
    versions = store.list_versions("alice", "j1")
    assert [v.version for v in versions] == [1, 2, 3]


def test_get_version_hit_and_miss(store: DynamoDBLetterStore) -> None:
    _save_basic(store)
    _save_basic(store)
    assert store.get_version("alice", "j1", 2) is not None
    assert store.get_version("alice", "j1", 99) is None


def test_strategy_and_critique_round_trip(
    store: DynamoDBLetterStore,
) -> None:
    saved = _save_basic(
        store,
        strategy={"primary_project": "ML platform", "fit_score": 0.9},
        critique={"verdict": "approved", "scores": {"clarity": 9}},
    )
    fetched = store.get_version("alice", "j1", saved.version)
    assert fetched is not None
    assert fetched.strategy == {"primary_project": "ML platform", "fit_score": 0.9}
    assert fetched.critique == {"verdict": "approved", "scores": {"clarity": 9}}


def test_count_refinements_returns_max(store: DynamoDBLetterStore) -> None:
    store.save_letter(
        "alice", "j1", text="v1", strategy=None, critique=None,
        refinement_index=0,
    )
    store.save_letter(
        "alice", "j1", text="v2", strategy=None, critique=None,
        refinement_index=1,
    )
    store.save_letter(
        "alice", "j1", text="v3", strategy=None, critique=None,
        refinement_index=3,
    )
    assert store.count_refinements("alice", "j1") == 3


def test_count_refinements_zero_when_no_letters(
    store: DynamoDBLetterStore,
) -> None:
    assert store.count_refinements("alice", "ghost") == 0


def test_delete_all_versions_clears_one_jobs_letters(
    store: DynamoDBLetterStore,
) -> None:
    _save_basic(store)
    _save_basic(store)
    store.save_letter(
        "alice", "j2", text="other", strategy=None, critique=None
    )
    store.delete_all_versions("alice", "j1")
    assert store.list_versions("alice", "j1") == []
    assert len(store.list_versions("alice", "j2")) == 1


def test_delete_all_versions_noop_when_absent(
    store: DynamoDBLetterStore,
) -> None:
    # Should not raise.
    store.delete_all_versions("alice", "ghost")


def test_per_user_isolation(store: DynamoDBLetterStore) -> None:
    store.save_letter(
        "alice", "j1", text="a", strategy=None, critique=None
    )
    store.save_letter(
        "bob", "j1", text="b", strategy=None, critique=None
    )
    assert len(store.list_versions("alice", "j1")) == 1
    assert len(store.list_versions("bob", "j1")) == 1


def test_job_id_with_special_chars_round_trips(
    store: DynamoDBLetterStore,
) -> None:
    """Base64-ish job IDs (containing '/' or '=') must work."""
    job_id = "abc/def==xyz"
    saved = store.save_letter(
        "alice", job_id, text="hello", strategy=None, critique=None
    )
    fetched = store.get_version("alice", job_id, saved.version)
    assert fetched is not None
    assert fetched.job_id == job_id
