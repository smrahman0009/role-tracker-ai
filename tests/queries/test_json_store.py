"""Tests for the JSON-file-backed query store."""

import json
from pathlib import Path

import pytest

from role_tracker.queries.json_store import JsonQueryStore


@pytest.fixture
def store(tmp_path: Path) -> JsonQueryStore:
    return JsonQueryStore(
        root=tmp_path / "queries",
        bootstrap_yaml_root=tmp_path / "users",
    )


@pytest.fixture
def store_with_yaml_bootstrap(tmp_path: Path) -> JsonQueryStore:
    """Store with a users/foo.yaml fixture available for bootstrap."""
    yaml_dir = tmp_path / "users"
    yaml_dir.mkdir()
    (yaml_dir / "alice.yaml").write_text(
        "id: alice\n"
        "name: Alice\n"
        "resume_path: data/resumes/alice.pdf\n"
        "queries:\n"
        '  - what: "data scientist"\n'
        '    where: "canada"\n'
        '  - what: "ML engineer"\n'
        '    where: "toronto"\n'
    )
    return JsonQueryStore(
        root=tmp_path / "queries",
        bootstrap_yaml_root=yaml_dir,
    )


def test_list_empty_when_no_yaml_no_json(store: JsonQueryStore) -> None:
    assert store.list_queries("nobody") == []


def test_first_read_bootstraps_from_yaml(
    store_with_yaml_bootstrap: JsonQueryStore,
) -> None:
    queries = store_with_yaml_bootstrap.list_queries("alice")
    assert len(queries) == 2
    assert {q.what for q in queries} == {"data scientist", "ML engineer"}


def test_bootstrap_persists_to_json(
    store_with_yaml_bootstrap: JsonQueryStore, tmp_path: Path
) -> None:
    store_with_yaml_bootstrap.list_queries("alice")
    json_path = tmp_path / "queries" / "alice.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["version"] == 1
    assert len(data["queries"]) == 2


def test_add_query_returns_record_with_id(store: JsonQueryStore) -> None:
    saved = store.add_query("alice", what="data scientist", where="canada")
    assert saved.query_id
    assert saved.what == "data scientist"
    assert saved.where == "canada"
    assert saved.enabled is True


def test_add_query_persists_across_instances(
    store: JsonQueryStore, tmp_path: Path
) -> None:
    store.add_query("alice", what="data scientist", where="canada")
    fresh = JsonQueryStore(
        root=tmp_path / "queries",
        bootstrap_yaml_root=tmp_path / "users",
    )
    queries = fresh.list_queries("alice")
    assert len(queries) == 1
    assert queries[0].what == "data scientist"


def test_get_query_finds_existing(store: JsonQueryStore) -> None:
    saved = store.add_query("alice", what="x", where="y")
    found = store.get_query("alice", saved.query_id)
    assert found is not None
    assert found.query_id == saved.query_id


def test_get_query_returns_none_when_missing(store: JsonQueryStore) -> None:
    assert store.get_query("alice", "nonexistent") is None


def test_update_query_patches_only_provided_fields(store: JsonQueryStore) -> None:
    saved = store.add_query("alice", what="data scientist", where="canada")
    updated = store.update_query("alice", saved.query_id, where="toronto")
    assert updated is not None
    assert updated.what == "data scientist"  # unchanged
    assert updated.where == "toronto"        # patched
    assert updated.enabled is True           # unchanged


def test_update_query_can_disable(store: JsonQueryStore) -> None:
    saved = store.add_query("alice", what="x", where="y")
    updated = store.update_query("alice", saved.query_id, enabled=False)
    assert updated is not None
    assert updated.enabled is False


def test_update_query_returns_none_when_missing(store: JsonQueryStore) -> None:
    assert store.update_query("alice", "nonexistent", what="x") is None


def test_delete_query_removes(store: JsonQueryStore) -> None:
    saved = store.add_query("alice", what="x", where="y")
    assert store.delete_query("alice", saved.query_id) is True
    assert store.list_queries("alice") == []


def test_delete_query_returns_false_when_missing(store: JsonQueryStore) -> None:
    assert store.delete_query("alice", "nonexistent") is False


def test_users_are_isolated(store: JsonQueryStore) -> None:
    store.add_query("alice", what="data", where="canada")
    store.add_query("bob", what="ml", where="toronto")
    assert len(store.list_queries("alice")) == 1
    assert len(store.list_queries("bob")) == 1
    assert store.list_queries("alice")[0].what == "data"
