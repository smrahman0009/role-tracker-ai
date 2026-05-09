"""Tests for DynamoDBUserProfileStore — same Protocol as YamlUserProfileStore."""

from pathlib import Path

import pytest

from role_tracker.aws.dynamodb_user_profile_store import (
    DynamoDBUserProfileStore,
    UserProfileNotFoundError,
)
from role_tracker.config import JobQuery
from role_tracker.users.models import UserProfile
from tests.aws.conftest import make_users_table

TABLE_NAME = "role-tracker-users"


@pytest.fixture
def store(dynamodb_resource: object) -> DynamoDBUserProfileStore:
    make_users_table(dynamodb_resource, TABLE_NAME)
    return DynamoDBUserProfileStore(
        TABLE_NAME, dynamodb_resource=dynamodb_resource
    )


def _profile(user_id: str = "alice", **overrides: object) -> UserProfile:
    fields = {
        "id": user_id,
        "name": "Alice Smith",
        "email": "alice@example.com",
        "phone": "555-0100",
        "city": "Toronto, ON",
        "linkedin_url": "https://linkedin.com/in/alice",
        "resume_path": Path(f"data/resumes/{user_id}.pdf"),
        "queries": [JobQuery(what="ML engineer", where="canada")],
    }
    fields.update(overrides)
    return UserProfile(**fields)


# ----- list / get -----------------------------------------------------------


def test_list_returns_empty_for_new_table(
    store: DynamoDBUserProfileStore,
) -> None:
    assert store.list_users() == []


def test_get_unknown_user_raises(store: DynamoDBUserProfileStore) -> None:
    with pytest.raises(UserProfileNotFoundError):
        store.get_user("ghost")


# ----- save round-trip -----------------------------------------------------


def test_save_then_get_round_trips(store: DynamoDBUserProfileStore) -> None:
    original = _profile("alice")
    store.save_user(original)
    fetched = store.get_user("alice")
    assert fetched.id == original.id
    assert fetched.name == original.name
    assert fetched.email == original.email
    assert fetched.linkedin_url == original.linkedin_url
    assert fetched.queries == original.queries
    assert fetched.resume_path == original.resume_path


def test_save_overwrites_existing(store: DynamoDBUserProfileStore) -> None:
    store.save_user(_profile("alice", name="Alice Smith"))
    store.save_user(_profile("alice", name="Alice Renamed"))
    assert store.get_user("alice").name == "Alice Renamed"


def test_save_preserves_show_in_header_flags(
    store: DynamoDBUserProfileStore,
) -> None:
    """The boolean flags that control which contact fields render
    in the cover-letter header have to round-trip exactly."""
    store.save_user(
        _profile(
            "alice",
            show_phone_in_header=False,
            show_linkedin_in_header=False,
        )
    )
    fetched = store.get_user("alice")
    assert fetched.show_phone_in_header is False
    assert fetched.show_email_in_header is True  # default
    assert fetched.show_linkedin_in_header is False


def test_save_preserves_exclude_lists(
    store: DynamoDBUserProfileStore,
) -> None:
    store.save_user(
        _profile(
            "alice",
            exclude_companies=["Foo Inc", "Bar LLC"],
            exclude_title_keywords=["intern"],
            exclude_publishers=["LinkedIn"],
        )
    )
    fetched = store.get_user("alice")
    assert fetched.exclude_companies == ["Foo Inc", "Bar LLC"]
    assert fetched.exclude_title_keywords == ["intern"]
    assert fetched.exclude_publishers == ["LinkedIn"]


# ----- list_users ----------------------------------------------------------


def test_list_returns_all_saved_users(
    store: DynamoDBUserProfileStore,
) -> None:
    store.save_user(_profile("alice"))
    store.save_user(_profile("bob", name="Bob Jones"))
    store.save_user(_profile("carol", name="Carol Wu"))
    listed = store.list_users()
    assert [u.id for u in listed] == ["alice", "bob", "carol"]


def test_list_isolates_users_from_each_others_data(
    store: DynamoDBUserProfileStore,
) -> None:
    """Each item is fully self-contained; no field bleed-through."""
    store.save_user(
        _profile("alice", linkedin_url="https://linkedin.com/in/alice")
    )
    store.save_user(
        _profile("bob", linkedin_url="https://linkedin.com/in/bob")
    )
    listed = {u.id: u.linkedin_url for u in store.list_users()}
    assert listed["alice"] == "https://linkedin.com/in/alice"
    assert listed["bob"] == "https://linkedin.com/in/bob"
