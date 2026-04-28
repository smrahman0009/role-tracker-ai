"""Tests for the FileLetterStore."""

from pathlib import Path

import pytest

from role_tracker.letters.store import FileLetterStore


@pytest.fixture
def store(tmp_path: Path) -> FileLetterStore:
    return FileLetterStore(root=tmp_path / "letters")


def test_list_versions_empty(store: FileLetterStore) -> None:
    assert store.list_versions("alice", "job_a") == []


def test_save_assigns_version_1(store: FileLetterStore) -> None:
    saved = store.save_letter(
        "alice",
        "job_a",
        text="Hello,\n\nBody is\n\nfour words.",
        strategy={"primary_project": "p"},
        critique={"verdict": "approved"},
    )
    assert saved.version == 1
    assert saved.word_count == 5  # Hello, / Body / is / four / words.
    assert saved.feedback_used is None


def test_save_increments_version(store: FileLetterStore) -> None:
    store.save_letter("alice", "job_a", text="v1", strategy={}, critique={})
    store.save_letter("alice", "job_a", text="v2", strategy={}, critique={})
    third = store.save_letter(
        "alice", "job_a", text="v3", strategy={}, critique={}
    )
    assert third.version == 3
    assert {v.version for v in store.list_versions("alice", "job_a")} == {1, 2, 3}


def test_versions_per_job_independent(store: FileLetterStore) -> None:
    store.save_letter("alice", "job_a", text="x", strategy={}, critique={})
    store.save_letter("alice", "job_b", text="y", strategy={}, critique={})
    saved = store.save_letter(
        "alice", "job_a", text="z", strategy={}, critique={}
    )
    assert saved.version == 2
    assert store.get_version("alice", "job_b", 1).text == "y"


def test_get_version_returns_none_for_missing(store: FileLetterStore) -> None:
    assert store.get_version("alice", "job_a", 99) is None


def test_users_isolated(store: FileLetterStore) -> None:
    store.save_letter("alice", "job_a", text="alice", strategy={}, critique={})
    store.save_letter("bob", "job_a", text="bob", strategy={}, critique={})
    assert store.get_version("alice", "job_a", 1).text == "alice"
    assert store.get_version("bob", "job_a", 1).text == "bob"


def test_handles_url_unsafe_job_ids(store: FileLetterStore) -> None:
    """JSearch IDs sometimes contain '=' or '/' — those need sanitizing."""
    weird_id = "abc/123==/xyz"
    store.save_letter("alice", weird_id, text="x", strategy={}, critique={})
    assert store.get_version("alice", weird_id, 1) is not None


def test_feedback_used_persists(store: FileLetterStore) -> None:
    saved = store.save_letter(
        "alice",
        "job_a",
        text="x",
        strategy={},
        critique={},
        feedback_used="make it shorter",
    )
    assert saved.feedback_used == "make it shorter"
    fetched = store.get_version("alice", "job_a", 1)
    assert fetched.feedback_used == "make it shorter"
