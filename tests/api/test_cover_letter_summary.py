"""Tests for POST /users/{id}/jobs/{job_id}/cover-letter/summary
and the model picker on the draft route."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from role_tracker.api.main import create_app
from role_tracker.api.routes.jobs import (
    get_seen_jobs_store,
    get_usage_store,
)
from role_tracker.api.routes.letters import (
    get_anthropic_client,
    get_letter_store,
    get_user_profile_store,
)
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.cover_letter.interactive import HAIKU_MODEL, SONNET_MODEL
from role_tracker.jobs.models import JobPosting
from role_tracker.jobs.seen import FileSeenJobsStore
from role_tracker.letters.store import FileLetterStore
from role_tracker.matching.scorer import ScoredJob
from role_tracker.resume.store import FileResumeStore
from role_tracker.usage import FileUsageStore
from role_tracker.users.yaml_store import YamlUserProfileStore

# ----- stubs ---------------------------------------------------------------


class _TextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)]


class _Messages:
    """Records the model used for each call so tests can assert on it."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict] = []

    def create(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        return _Response(self._text)


class _StubAnthropic:
    def __init__(self, text: str = "Generated text.") -> None:
        self.messages = _Messages(text)


# ----- helpers -------------------------------------------------------------


def _job() -> JobPosting:
    return JobPosting(
        id="j1",
        title="Senior Data Scientist",
        company="Shopify",
        location="Toronto",
        description=(
            "We're hiring a senior DS. 5+ years Python, ML platform "
            "experience. Hybrid role in Toronto."
        ),
        url="https://example.com",
        posted_at="2026-04-28T00:00:00Z",
        source="jsearch",
        publisher="Shopify Careers",
    )


_VALID_SUMMARY_PAYLOAD = json.dumps(
    {
        "role": "Senior data scientist on Shopify's Risk team.",
        "requirements": "Python and 5+ years production ML experience.",
        "context": "Hybrid in Toronto. Suits builders shipping ML to prod.",
    }
)


def _make_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    anthropic_text: str = _VALID_SUMMARY_PAYLOAD,
) -> tuple[TestClient, _StubAnthropic]:
    import role_tracker.api.routes.letters as letters_module

    monkeypatch.setattr(letters_module, "parse_resume", lambda _: "fake resume text")

    app = create_app()

    seen_store = FileSeenJobsStore(root=tmp_path / "seen")
    seen_store.upsert_many("alice", [ScoredJob(job=_job(), score=0.9)])

    resume_store = FileResumeStore(root=tmp_path / "resumes")
    resume_store.save_resume("alice", content=b"%PDF-fake", filename="alice.pdf")

    users_root = tmp_path / "users"
    users_root.mkdir()
    (users_root / "alice.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "alice",
                "name": "Alice Smith",
                "resume_path": str(tmp_path / "fake.pdf"),
                "queries": [],
            }
        )
    )

    stub_anthropic = _StubAnthropic(anthropic_text)

    app.dependency_overrides[get_resume_store] = lambda: resume_store
    app.dependency_overrides[get_seen_jobs_store] = lambda: seen_store
    app.dependency_overrides[get_letter_store] = lambda: FileLetterStore(
        root=tmp_path / "letters"
    )
    app.dependency_overrides[get_user_profile_store] = lambda: YamlUserProfileStore(
        root=users_root
    )
    app.dependency_overrides[get_usage_store] = lambda: FileUsageStore(
        root=tmp_path / "usage"
    )
    app.dependency_overrides[get_anthropic_client] = lambda: stub_anthropic

    return TestClient(app), stub_anthropic


@pytest.fixture
def client_and_stub(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[tuple[TestClient, _StubAnthropic]]:
    c, s = _make_client(monkeypatch, tmp_path)
    with c:
        yield c, s


# ----- /summary -----------------------------------------------------------


def test_summary_returns_three_sections_and_model(
    client_and_stub: tuple[TestClient, _StubAnthropic],
) -> None:
    client, _ = client_and_stub
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/summary",
        json={},  # all defaults
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"].startswith("Senior data scientist")
    assert "Python" in body["requirements"]
    assert "Hybrid" in body["context"]
    assert body["model"] == SONNET_MODEL


def test_summary_502_when_model_returns_garbage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If the model returns prose instead of JSON, surface a 502."""
    c, _ = _make_client(monkeypatch, tmp_path, anthropic_text="not json")
    with c:
        response = c.post(
            "/users/alice/jobs/j1/cover-letter/summary", json={}
        )
        assert response.status_code == 502


def test_summary_default_is_sonnet(
    client_and_stub: tuple[TestClient, _StubAnthropic],
) -> None:
    client, stub = client_and_stub
    client.post(
        "/users/alice/jobs/j1/cover-letter/summary", json={}
    )
    assert stub.messages.calls[-1]["model"] == SONNET_MODEL


def test_summary_honours_haiku_choice(
    client_and_stub: tuple[TestClient, _StubAnthropic],
) -> None:
    client, stub = client_and_stub
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/summary",
        json={"model": "haiku"},
    )
    assert response.status_code == 200
    assert response.json()["model"] == HAIKU_MODEL
    assert stub.messages.calls[-1]["model"] == HAIKU_MODEL


def test_summary_404_on_unknown_job(
    client_and_stub: tuple[TestClient, _StubAnthropic],
) -> None:
    client, _ = client_and_stub
    response = client.post(
        "/users/alice/jobs/missing/cover-letter/summary", json={}
    )
    assert response.status_code == 404


def test_summary_records_usage(
    client_and_stub: tuple[TestClient, _StubAnthropic],
) -> None:
    client, _ = client_and_stub
    client.post("/users/alice/jobs/j1/cover-letter/summary", json={})
    usage = client.get("/users/alice/usage").json()
    feature_calls = {
        f["feature"]: f["count"] for f in usage["current"]["feature_calls"]
    }
    assert feature_calls.get("cover_letter_summary") == 1


def test_summary_rejects_invalid_model_alias(
    client_and_stub: tuple[TestClient, _StubAnthropic],
) -> None:
    client, _ = client_and_stub
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/summary",
        json={"model": "opus"},
    )
    assert response.status_code == 422


# ----- /draft model picker (Phase 2.5 retroactive change) -----------------


def _draft_body(model: str | None = None) -> dict:
    body = {
        "paragraph": "hook",
        "analysis": {
            "strong": [],
            "gaps": [],
            "partial": [],
            "excitement_hooks": [],
            "model": "claude-haiku-4-5",
        },
        "committed": {"hook": None, "fit": None, "close": None},
    }
    if model is not None:
        body["model"] = model
    return body


def test_draft_default_model_is_sonnet(
    client_and_stub: tuple[TestClient, _StubAnthropic],
) -> None:
    """Phase 2 used Haiku by default; Phase 2.5 flips this to Sonnet."""
    client, stub = client_and_stub
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/draft", json=_draft_body()
    )
    assert response.status_code == 200
    assert response.json()["model"] == SONNET_MODEL
    assert stub.messages.calls[-1]["model"] == SONNET_MODEL


def test_draft_explicit_haiku(
    client_and_stub: tuple[TestClient, _StubAnthropic],
) -> None:
    client, stub = client_and_stub
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/draft",
        json=_draft_body(model="haiku"),
    )
    assert response.json()["model"] == HAIKU_MODEL
    assert stub.messages.calls[-1]["model"] == HAIKU_MODEL


def test_draft_rejects_invalid_model(
    client_and_stub: tuple[TestClient, _StubAnthropic],
) -> None:
    client, _ = client_and_stub
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/draft",
        json=_draft_body(model="opus"),
    )
    assert response.status_code == 422
