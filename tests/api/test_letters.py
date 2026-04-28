"""Tests for the cover-letter API routes.

The Phase 4 agent (`generate_cover_letter_agent`) is monkeypatched so no
real Anthropic calls happen. The mock simulates the agent's
usage_tracker output (strategy + last_critique) so we can verify the
full request → background task → poll → letter retrieval flow.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from role_tracker.api.main import create_app
from role_tracker.api.routes.jobs import get_jobs_cache
from role_tracker.api.routes.letters import (
    get_anthropic_client,
    get_letter_generation_store,
    get_letter_store,
    get_user_profile_store,
)
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.jobs.cache import FileJobsCache
from role_tracker.jobs.models import JobPosting
from role_tracker.letters.generation_state import FileLetterGenerationStore
from role_tracker.letters.store import FileLetterStore
from role_tracker.matching.scorer import ScoredJob
from role_tracker.resume.store import FileResumeStore
from role_tracker.users.models import UserProfile


class _StubUserProfileStore:
    """Returns a deterministic UserProfile for any user_id."""

    def get_user(self, user_id: str) -> UserProfile:
        return UserProfile(
            id=user_id,
            name=f"{user_id.title()} Test",
            email=f"{user_id}@example.com",
            phone="555-0100",
            city="Toronto, ON",
            resume_path=Path(f"data/resumes/{user_id}.pdf"),
            queries=[],
        )

    def list_users(self) -> list[UserProfile]:
        return []


_FAKE_PDF = b"%PDF-1.4\n% fake\n%%EOF\n"
_FAKE_LETTER = (
    "**Shaikh Mushfikur Rahman**\n\n"
    "Hello,\n\nThis is the generated letter body. " * 30
    + "\n\nBest,\nShaikh"
)
_FAKE_STRATEGY = {
    "fit_assessment": "MEDIUM",
    "fit_reasoning": "Adjacent skills.",
    "narrative_angle": "Production NLP maps to ranking.",
    "primary_project": "Company Name Resolution",
    "secondary_project": None,
}
_FAKE_CRITIQUE = {
    "scores": {
        "hallucination": {"score": 25, "threshold_met": True},
        "tailoring": {"score": 18, "threshold_met": True},
    },
    "total": 95,
    "verdict": "approved",
    "priority_fixes": [],
    "notes": "Clean draft.",
}


def _job(job_id: str = "j1") -> JobPosting:
    return JobPosting(
        id=job_id,
        title="ML Engineer",
        company="Shopify",
        location="Toronto",
        description="Build recommenders.",
        url="https://example.com",
        posted_at="2026-04-28T00:00:00Z",
        source="jsearch",
        publisher="Shopify Careers",
    )


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    monkeypatch.delenv("APP_TOKEN", raising=False)

    # Stub the Phase 4 agent so no real Anthropic calls happen.
    import role_tracker.api.routes.letters as letters_module

    def fake_agent(
        *,
        user: Any,  # noqa: ARG001
        resume_text: str,  # noqa: ARG001
        job: JobPosting,  # noqa: ARG001
        client: Any,  # noqa: ARG001
        usage_tracker: dict | None = None,
        **_: Any,
    ) -> str:
        if usage_tracker is not None:
            usage_tracker["strategy"] = _FAKE_STRATEGY
            usage_tracker["last_critique"] = _FAKE_CRITIQUE
        return _FAKE_LETTER

    monkeypatch.setattr(letters_module, "generate_cover_letter_agent", fake_agent)

    # Don't actually parse a real PDF.
    monkeypatch.setattr(letters_module, "parse_resume", lambda _: "fake resume text")

    app = create_app()
    cache = FileJobsCache(root=tmp_path / "jobs")
    # Seed a snapshot so the /jobs/{job_id} lookup finds a job.
    cache.save_snapshot("alice", [ScoredJob(job=_job("j1"), score=0.9)])

    app.dependency_overrides[get_resume_store] = lambda: FileResumeStore(
        root=tmp_path / "resumes"
    )
    app.dependency_overrides[get_jobs_cache] = lambda: cache
    app.dependency_overrides[get_letter_store] = lambda: FileLetterStore(
        root=tmp_path / "letters"
    )
    app.dependency_overrides[get_letter_generation_store] = (
        lambda: FileLetterGenerationStore(root=tmp_path / "letters")
    )
    app.dependency_overrides[get_user_profile_store] = lambda: _StubUserProfileStore()
    app.dependency_overrides[get_anthropic_client] = lambda: object()  # unused

    with TestClient(app) as c:
        yield c


def _seed_resume(client: TestClient, user_id: str = "alice") -> None:
    client.post(
        f"/users/{user_id}/resume",
        files={"file": ("r.pdf", _FAKE_PDF, "application/pdf")},
    )


# ----- generate -----


def test_generate_returns_202_and_id(client: TestClient) -> None:
    _seed_resume(client)
    response = client.post("/users/alice/jobs/j1/letters", json={})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["generation_id"]


def test_generate_completes_and_saves(client: TestClient) -> None:
    _seed_resume(client)
    gen_response = client.post("/users/alice/jobs/j1/letters", json={})
    generation_id = gen_response.json()["generation_id"]

    # TestClient runs BackgroundTasks synchronously after the response.
    poll = client.get(f"/users/alice/letter-jobs/{generation_id}")
    body = poll.json()
    assert body["status"] == "done"
    assert body["letter"] is not None
    assert body["letter"]["version"] == 1
    assert body["letter"]["text"].startswith("**Shaikh")
    assert body["letter"]["strategy"]["primary_project"] == "Company Name Resolution"
    assert body["letter"]["critique"]["verdict"] == "approved"


def test_generate_fails_without_resume(client: TestClient) -> None:
    gen_response = client.post("/users/alice/jobs/j1/letters", json={})
    poll = client.get(
        f"/users/alice/letter-jobs/{gen_response.json()['generation_id']}"
    )
    body = poll.json()
    assert body["status"] == "failed"
    assert "resume" in body["error"].lower()


def test_generate_fails_when_job_not_in_snapshot(client: TestClient) -> None:
    _seed_resume(client)
    gen_response = client.post("/users/alice/jobs/nonexistent/letters", json={})
    poll = client.get(
        f"/users/alice/letter-jobs/{gen_response.json()['generation_id']}"
    )
    body = poll.json()
    assert body["status"] == "failed"
    assert "not in current snapshot" in body["error"].lower()


# ----- regenerate -----


def test_regenerate_creates_new_version(client: TestClient) -> None:
    _seed_resume(client)
    # Generate v1
    gen1 = client.post("/users/alice/jobs/j1/letters", json={})
    client.get(f"/users/alice/letter-jobs/{gen1.json()['generation_id']}")
    # Regenerate → v2
    gen2 = client.post("/users/alice/jobs/j1/regenerate")
    assert gen2.status_code == 202
    poll = client.get(f"/users/alice/letter-jobs/{gen2.json()['generation_id']}")
    assert poll.json()["letter"]["version"] == 2


# ----- list versions -----


def test_list_versions_empty(client: TestClient) -> None:
    response = client.get("/users/alice/jobs/j1/letters")
    assert response.json() == {"versions": [], "total": 0}


def test_list_versions_returns_latest_first(client: TestClient) -> None:
    _seed_resume(client)
    gen1 = client.post("/users/alice/jobs/j1/letters", json={})
    client.get(f"/users/alice/letter-jobs/{gen1.json()['generation_id']}")
    gen2 = client.post("/users/alice/jobs/j1/regenerate")
    client.get(f"/users/alice/letter-jobs/{gen2.json()['generation_id']}")

    response = client.get("/users/alice/jobs/j1/letters")
    body = response.json()
    assert body["total"] == 2
    assert body["versions"][0]["version"] == 2  # latest first
    assert body["versions"][1]["version"] == 1


# ----- get one version -----


def test_get_version_returns_full_content(client: TestClient) -> None:
    _seed_resume(client)
    gen = client.post("/users/alice/jobs/j1/letters", json={})
    client.get(f"/users/alice/letter-jobs/{gen.json()['generation_id']}")

    response = client.get("/users/alice/jobs/j1/letters/1")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["text"]
    assert body["strategy"]["fit_assessment"] == "MEDIUM"


def test_get_version_404_for_missing(client: TestClient) -> None:
    response = client.get("/users/alice/jobs/j1/letters/99")
    assert response.status_code == 404


# ----- download -----


def test_download_md(client: TestClient) -> None:
    _seed_resume(client)
    gen = client.post("/users/alice/jobs/j1/letters", json={})
    client.get(f"/users/alice/letter-jobs/{gen.json()['generation_id']}")

    response = client.get("/users/alice/jobs/j1/letters/1/download.md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert b"Shaikh" in response.content


def test_download_404_for_missing(client: TestClient) -> None:
    response = client.get("/users/alice/jobs/j1/letters/99/download.md")
    assert response.status_code == 404


# ----- poll -----


def test_poll_404_for_unknown_generation(client: TestClient) -> None:
    response = client.get("/users/alice/letter-jobs/nonexistent")
    assert response.status_code == 404
