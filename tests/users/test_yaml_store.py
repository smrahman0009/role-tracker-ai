"""Tests for the YAML-backed UserProfileStore."""

from pathlib import Path
from textwrap import dedent

import pytest

from role_tracker.users.yaml_store import YamlUserProfileStore


def _write(path: Path, body: str) -> None:
    path.write_text(dedent(body).strip() + "\n")


@pytest.fixture
def sample_user_dir(tmp_path: Path) -> Path:
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    _write(
        users_dir / "alice.yaml",
        """
        id: alice
        name: Alice Example
        email: alice@example.com
        resume_path: data/resumes/alice.pdf
        top_n_jobs: 3
        queries:
          - what: data scientist
            where: canada
        exclude_companies:
          - bank
        exclude_title_keywords:
          - banking
        """,
    )
    _write(
        users_dir / "bob.yaml",
        """
        id: bob
        name: Bob Example
        resume_path: data/resumes/bob.pdf
        queries:
          - what: software engineer
            where: toronto
        """,
    )
    return users_dir


def test_list_users_returns_all_profiles(sample_user_dir: Path) -> None:
    store = YamlUserProfileStore(root=sample_user_dir)
    users = store.list_users()
    assert [u.id for u in users] == ["alice", "bob"]


def test_get_user_by_id(sample_user_dir: Path) -> None:
    store = YamlUserProfileStore(root=sample_user_dir)
    alice = store.get_user("alice")
    assert alice.name == "Alice Example"
    assert alice.top_n_jobs == 3
    assert alice.exclude_companies == ["bank"]
    assert alice.queries[0].what == "data scientist"


def test_get_user_unknown_id_raises(sample_user_dir: Path) -> None:
    store = YamlUserProfileStore(root=sample_user_dir)
    with pytest.raises(FileNotFoundError, match="No user profile"):
        store.get_user("nobody")


def test_user_with_defaults(sample_user_dir: Path) -> None:
    store = YamlUserProfileStore(root=sample_user_dir)
    bob = store.get_user("bob")
    assert bob.top_n_jobs == 5  # default
    assert bob.exclude_companies == []
    assert bob.email == ""


def test_resume_embedding_cache_path_is_derived_from_resume(
    sample_user_dir: Path,
) -> None:
    store = YamlUserProfileStore(root=sample_user_dir)
    alice = store.get_user("alice")
    assert alice.resume_embedding_cache_path == Path(
        "data/resumes/alice.embedding.json"
    )


def test_list_users_on_missing_dir_returns_empty(tmp_path: Path) -> None:
    store = YamlUserProfileStore(root=tmp_path / "nonexistent")
    assert store.list_users() == []
