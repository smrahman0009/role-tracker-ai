"""Tests for the Phase 2 routes:
- POST /users/{id}/jobs/{job_id}/cover-letter/draft
- POST /users/{id}/jobs/{job_id}/cover-letter/finalize
"""

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
from role_tracker.jobs.models import JobPosting
from role_tracker.jobs.seen import FileSeenJobsStore
from role_tracker.letters.store import FileLetterStore
from role_tracker.matching.scorer import ScoredJob
from role_tracker.resume.store import FileResumeStore
from role_tracker.usage import FileUsageStore
from role_tracker.users.yaml_store import YamlUserProfileStore

# ----- stubs --------------------------------------------------------------


class _TextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)]


class _Messages:
    def __init__(self, text: str) -> None:
        self._text = text
        self.last_request: dict | None = None

    def create(self, **kwargs: Any) -> _Response:
        self.last_request = kwargs
        return _Response(self._text)


class _StubAnthropic:
    def __init__(self, text: str = "Generated paragraph here.") -> None:
        self.messages = _Messages(text)


# ----- helpers ------------------------------------------------------------


def _job() -> JobPosting:
    return JobPosting(
        id="j1",
        title="Senior Data Scientist",
        company="Shopify",
        location="Toronto",
        description=(
            "We're hiring a senior DS with Python, ML, and a focus on "
            "real-time inference."
        ),
        url="https://example.com",
        posted_at="2026-04-28T00:00:00Z",
        source="jsearch",
        publisher="Shopify Careers",
    )


def _seed_user_profile(tmp_path: Path) -> YamlUserProfileStore:
    users_root = tmp_path / "users"
    users_root.mkdir()
    (users_root / "alice.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "alice",
                "name": "Alice Smith",
                "email": "alice@example.com",
                "resume_path": str(tmp_path / "fake.pdf"),
                "queries": [],
            }
        )
    )
    return YamlUserProfileStore(root=users_root)


def _make_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    anthropic_text: str = "Generated paragraph here.",
    seed_resume: bool = True,
    seed_job: bool = True,
) -> TestClient:
    import role_tracker.api.routes.letters as letters_module

    monkeypatch.setattr(letters_module, "parse_resume", lambda _: "fake resume text")

    app = create_app()

    seen_store = FileSeenJobsStore(root=tmp_path / "seen")
    if seed_job:
        seen_store.upsert_many("alice", [ScoredJob(job=_job(), score=0.9)])

    resume_store = FileResumeStore(root=tmp_path / "resumes")
    if seed_resume:
        resume_store.save_resume("alice", content=b"%PDF-fake", filename="alice.pdf")

    letter_store = FileLetterStore(root=tmp_path / "letters")
    user_store = _seed_user_profile(tmp_path)
    usage_store = FileUsageStore(root=tmp_path / "usage")

    app.dependency_overrides[get_resume_store] = lambda: resume_store
    app.dependency_overrides[get_seen_jobs_store] = lambda: seen_store
    app.dependency_overrides[get_letter_store] = lambda: letter_store
    app.dependency_overrides[get_user_profile_store] = lambda: user_store
    app.dependency_overrides[get_usage_store] = lambda: usage_store
    app.dependency_overrides[get_anthropic_client] = lambda: _StubAnthropic(
        anthropic_text
    )

    return TestClient(app)


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    with _make_client(monkeypatch, tmp_path) as c:
        yield c


def _draft_body(paragraph: str = "hook") -> dict:
    return {
        "paragraph": paragraph,
        "analysis": {
            "strong": ["Python, 5 yrs"],
            "gaps": [],
            "partial": ["Distributed systems, 1 yr"],
            "excitement_hooks": ["their focus on real-time inference"],
            "model": "claude-haiku-4-5",
        },
        "committed": {"hook": None, "fit": None, "close": None},
    }


# ----- /draft -------------------------------------------------------------


def test_draft_returns_paragraph_and_model(client: TestClient) -> None:
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/draft",
        json=_draft_body("hook"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["paragraph"] == "hook"
    assert body["text"] == "Generated paragraph here."
    assert body["model"].startswith("claude-haiku-")


def test_draft_supports_all_three_paragraphs(client: TestClient) -> None:
    for paragraph in ("hook", "fit", "close"):
        response = client.post(
            "/users/alice/jobs/j1/cover-letter/draft",
            json=_draft_body(paragraph),
        )
        assert response.status_code == 200, paragraph
        assert response.json()["paragraph"] == paragraph


def test_draft_404_when_job_unknown(client: TestClient) -> None:
    response = client.post(
        "/users/alice/jobs/missing/cover-letter/draft",
        json=_draft_body(),
    )
    assert response.status_code == 404


def test_draft_400_when_resume_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with _make_client(monkeypatch, tmp_path, seed_resume=False) as client:
        response = client.post(
            "/users/alice/jobs/j1/cover-letter/draft",
            json=_draft_body(),
        )
        assert response.status_code == 400


def test_draft_records_usage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with _make_client(monkeypatch, tmp_path) as client:
        client.post(
            "/users/alice/jobs/j1/cover-letter/draft",
            json=_draft_body("hook"),
        )
        usage = client.get("/users/alice/usage").json()
        feature_calls = {
            f["feature"]: f["count"]
            for f in usage["current"]["feature_calls"]
        }
        assert feature_calls.get("cover_letter_draft") == 1


def test_draft_rejects_invalid_paragraph_value(client: TestClient) -> None:
    body = _draft_body()
    body["paragraph"] = "intro"  # not allowed
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/draft", json=body
    )
    assert response.status_code == 422  # pydantic validation


# ----- /finalize ----------------------------------------------------------


def test_finalize_saves_letter_with_edited_by_user(client: TestClient) -> None:
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/finalize",
        json={"hook": "Hello.", "fit": "Fit.", "close": "Best,\nAlice"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["edited_by_user"] is True
    assert body["version"] == 1
    assert "Hello." in body["text"]
    assert "Fit." in body["text"]
    assert "Best," in body["text"]


def test_finalize_increments_version(client: TestClient) -> None:
    body = {"hook": "h.", "fit": "f.", "close": "c."}
    r1 = client.post(
        "/users/alice/jobs/j1/cover-letter/finalize", json=body
    )
    r2 = client.post(
        "/users/alice/jobs/j1/cover-letter/finalize", json=body
    )
    assert r1.json()["version"] == 1
    assert r2.json()["version"] == 2


def test_finalize_400_on_blank_paragraph(client: TestClient) -> None:
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/finalize",
        json={"hook": "h.", "fit": "  ", "close": "c."},
    )
    assert response.status_code == 400


def test_finalize_letter_appears_in_versions_list(client: TestClient) -> None:
    """A finalized letter shows up alongside agent-generated ones."""
    client.post(
        "/users/alice/jobs/j1/cover-letter/finalize",
        json={"hook": "h.", "fit": "f.", "close": "c."},
    )
    versions = client.get(
        "/users/alice/jobs/j1/letters"
    ).json()
    assert versions["total"] == 1
    assert versions["versions"][0]["edited_by_user"] is True
