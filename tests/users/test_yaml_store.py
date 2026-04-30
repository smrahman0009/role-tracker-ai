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
    assert bob.top_n_jobs == 50  # default (browsable list)
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


def test_contact_header_includes_all_populated_fields(tmp_path: Path) -> None:
    (tmp_path).mkdir(exist_ok=True)
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    _write(
        users_dir / "full.yaml",
        """
        id: full
        name: Jane Doe
        email: jane@example.com
        phone: 555-1234
        city: Toronto, ON
        linkedin_url: https://linkedin.com/in/jane
        github_url: https://github.com/jane
        resume_path: data/resumes/jane.pdf
        queries: []
        """,
    )
    user = YamlUserProfileStore(root=users_dir).get_user("full")
    header = user.contact_header()
    assert "Jane Doe" in header
    assert "555-1234" in header
    assert "Toronto, ON" in header
    assert "jane@example.com" in header
    assert "[LinkedIn](https://linkedin.com/in/jane)" in header
    assert "[GitHub](https://github.com/jane)" in header


def test_contact_header_respects_show_flags(tmp_path: Path) -> None:
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    _write(
        users_dir / "alice.yaml",
        """
        id: alice
        name: Alice
        phone: "555-1234"
        email: a@b.com
        city: Toronto
        linkedin_url: https://linkedin.com/in/alice
        show_phone_in_header: false
        show_linkedin_in_header: false
        resume_path: data/resumes/alice.pdf
        queries: []
        """,
    )
    user = YamlUserProfileStore(root=users_dir).get_user("alice")
    header = user.contact_header()
    assert "555-1234" not in header        # phone hidden by flag
    assert "linkedin" not in header.lower()  # LinkedIn hidden by flag
    assert "a@b.com" in header              # email still shown
    assert "Toronto" in header              # city still shown
    assert "Alice" in header                # name always shown


def test_save_user_round_trip(tmp_path: Path) -> None:
    """save_user persists changes that survive a fresh store instance."""
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    _write(
        users_dir / "alice.yaml",
        """
        id: alice
        name: Alice
        resume_path: data/resumes/alice.pdf
        queries: []
        """,
    )
    store = YamlUserProfileStore(root=users_dir)
    user = store.get_user("alice")
    updated = user.model_copy(
        update={"phone": "999-0000", "show_email_in_header": False}
    )
    store.save_user(updated)

    fresh = YamlUserProfileStore(root=users_dir).get_user("alice")
    assert fresh.phone == "999-0000"
    assert fresh.show_email_in_header is False


def test_contact_header_skips_empty_fields(tmp_path: Path) -> None:
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    _write(
        users_dir / "min.yaml",
        """
        id: min
        name: Only Name
        resume_path: data/resumes/x.pdf
        queries: []
        """,
    )
    user = YamlUserProfileStore(root=users_dir).get_user("min")
    header = user.contact_header()
    assert "Only Name" in header
    assert "LinkedIn" not in header
    assert "GitHub" not in header
    # No dangling separators
    assert " |  " not in header
