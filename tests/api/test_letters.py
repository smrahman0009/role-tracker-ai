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
from role_tracker.api.routes.jobs import get_seen_jobs_store
from role_tracker.api.routes.letters import (
    get_anthropic_client,
    get_letter_generation_store,
    get_letter_store,
    get_user_profile_store,
)
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.jobs.models import JobPosting
from role_tracker.jobs.seen import FileSeenJobsStore
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
    seen_store = FileSeenJobsStore(root=tmp_path / "seen")
    # Seed the long-lived index so the /jobs/{job_id} lookup finds a job.
    seen_store.upsert_many("alice", [ScoredJob(job=_job("j1"), score=0.9)])

    app.dependency_overrides[get_resume_store] = lambda: FileResumeStore(
        root=tmp_path / "resumes"
    )
    app.dependency_overrides[get_seen_jobs_store] = lambda: seen_store
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


def test_download_pdf(client: TestClient) -> None:
    _seed_resume(client)
    gen = client.post("/users/alice/jobs/j1/letters", json={})
    client.get(f"/users/alice/letter-jobs/{gen.json()['generation_id']}")

    response = client.get("/users/alice/jobs/j1/letters/1/download.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.pdf"')
    # PDF magic header.
    assert response.content.startswith(b"%PDF-")


def test_download_docx(client: TestClient) -> None:
    _seed_resume(client)
    gen = client.post("/users/alice/jobs/j1/letters", json={})
    client.get(f"/users/alice/letter-jobs/{gen.json()['generation_id']}")

    response = client.get("/users/alice/jobs/j1/letters/1/download.docx")
    assert response.status_code == 200
    assert (
        "officedocument.wordprocessingml.document"
        in response.headers["content-type"]
    )
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.docx"')
    # DOCX is a zip archive.
    assert response.content.startswith(b"PK")


def test_download_pdf_404_for_missing(client: TestClient) -> None:
    response = client.get("/users/alice/jobs/j1/letters/99/download.pdf")
    assert response.status_code == 404


def test_download_docx_404_for_missing(client: TestClient) -> None:
    response = client.get("/users/alice/jobs/j1/letters/99/download.docx")
    assert response.status_code == 404


# ----- poll -----


def test_poll_404_for_unknown_generation(client: TestClient) -> None:
    response = client.get("/users/alice/letter-jobs/nonexistent")
    assert response.status_code == 404


# ----- refine -----


@pytest.fixture
def client_with_refine_stub(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    """Same fixture as `client` but also stubs out refine_cover_letter."""
    monkeypatch.delenv("APP_TOKEN", raising=False)

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

    def fake_refine(
        *,
        user: Any,  # noqa: ARG001
        resume_text: str,  # noqa: ARG001
        job: JobPosting,  # noqa: ARG001
        previous_letter: str,
        previous_strategy: dict,  # noqa: ARG001
        feedback: str,
        client: Any,  # noqa: ARG001
        **_: Any,
    ) -> str:
        # Echo the feedback so we can verify the parameter wiring.
        return f"REFINED [{feedback}]\n\n" + previous_letter

    monkeypatch.setattr(letters_module, "generate_cover_letter_agent", fake_agent)
    monkeypatch.setattr(letters_module, "refine_cover_letter", fake_refine)
    monkeypatch.setattr(letters_module, "parse_resume", lambda _: "fake resume text")

    app = create_app()
    seen_store = FileSeenJobsStore(root=tmp_path / "seen")
    seen_store.upsert_many("alice", [ScoredJob(job=_job("j1"), score=0.9)])

    app.dependency_overrides[get_resume_store] = lambda: FileResumeStore(
        root=tmp_path / "resumes"
    )
    app.dependency_overrides[get_seen_jobs_store] = lambda: seen_store
    app.dependency_overrides[get_letter_store] = lambda: FileLetterStore(
        root=tmp_path / "letters"
    )
    app.dependency_overrides[get_letter_generation_store] = (
        lambda: FileLetterGenerationStore(root=tmp_path / "letters")
    )
    app.dependency_overrides[get_user_profile_store] = lambda: _StubUserProfileStore()
    app.dependency_overrides[get_anthropic_client] = lambda: object()

    with TestClient(app) as c:
        yield c


def _generate_v1(client: TestClient) -> None:
    """Helper: seed a v1 letter so we have something to refine."""
    client.post(
        "/users/alice/resume",
        files={"file": ("r.pdf", _FAKE_PDF, "application/pdf")},
    )
    gen = client.post("/users/alice/jobs/j1/letters", json={})
    client.get(f"/users/alice/letter-jobs/{gen.json()['generation_id']}")


def test_refine_returns_202(client_with_refine_stub: TestClient) -> None:
    _generate_v1(client_with_refine_stub)
    response = client_with_refine_stub.post(
        "/users/alice/jobs/j1/letters/1/refine",
        json={"feedback": "Make it more technical"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "pending"


def test_refine_creates_new_version_with_feedback(
    client_with_refine_stub: TestClient,
) -> None:
    _generate_v1(client_with_refine_stub)
    refine_response = client_with_refine_stub.post(
        "/users/alice/jobs/j1/letters/1/refine",
        json={"feedback": "Shorter please"},
    )
    generation_id = refine_response.json()["generation_id"]

    poll = client_with_refine_stub.get(f"/users/alice/letter-jobs/{generation_id}")
    body = poll.json()
    assert body["status"] == "done"
    assert body["letter"]["version"] == 2
    assert "REFINED [Shorter please]" in body["letter"]["text"]
    assert body["letter"]["feedback_used"] == "Shorter please"
    # Strategy carries forward from v1
    assert body["letter"]["strategy"]["primary_project"] == "Company Name Resolution"


def test_refine_404_for_missing_source_version(
    client_with_refine_stub: TestClient,
) -> None:
    response = client_with_refine_stub.post(
        "/users/alice/jobs/j1/letters/99/refine",
        json={"feedback": "anything please"},
    )
    assert response.status_code == 404


def test_refine_validates_min_feedback_length(
    client_with_refine_stub: TestClient,
) -> None:
    _generate_v1(client_with_refine_stub)
    response = client_with_refine_stub.post(
        "/users/alice/jobs/j1/letters/1/refine", json={"feedback": "hi"}
    )
    assert response.status_code == 422  # Pydantic validation


def test_refine_cap_blocks_after_max_refinements(
    client_with_refine_stub: TestClient,
) -> None:
    """After 10 refinements on a letter, refine #11 must return 422."""
    _generate_v1(client_with_refine_stub)
    # Bump the v1 source version's refinement_index to MAX by saving a
    # synthetic version directly via the store (the test fixture uses
    # FileLetterStore in tmp_path).
    from role_tracker.api.routes.letters import get_letter_store

    # Find which dependency override is registered (the test client's app).
    app = client_with_refine_stub.app
    store = app.dependency_overrides[get_letter_store]()
    store.save_letter(
        "alice",
        "j1",
        text="x" * 10,
        strategy={"primary_project": "p"},
        critique=None,
        feedback_used="prev",
        refinement_index=10,
    )

    response = client_with_refine_stub.post(
        "/users/alice/jobs/j1/letters/1/refine",
        json={"feedback": "any feedback please"},
    )
    assert response.status_code == 422
    assert "cap" in response.json()["detail"].lower()


# ----- manual edit -----


def _make_valid_edit_text() -> str:
    """A 250-word edit body that passes the gentle deterministic checks."""
    return (
        "**Shaikh Mushfikur Rahman**\n\n"
        "Hello,\n\n"
        + ("word " * 100).strip()
        + "\n\n"
        + ("word " * 100).strip()
        + "\n\n"
        + "Best,\nShaikh"
    )


def test_manual_edit_returns_201_and_new_version(
    client_with_refine_stub: TestClient,
) -> None:
    _generate_v1(client_with_refine_stub)
    response = client_with_refine_stub.post(
        "/users/alice/jobs/j1/letters/1/edit",
        json={"text": _make_valid_edit_text()},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["version"] == 2
    assert body["edited_by_user"] is True
    assert body["feedback_used"] == "manual edit"
    assert body["critique"] is None
    # Strategy carries forward
    assert body["strategy"]["primary_project"] == "Company Name Resolution"
    # refinement_index NOT bumped
    assert body["refinement_index"] == 0


def test_manual_edit_rejects_too_few_words(
    client_with_refine_stub: TestClient,
) -> None:
    _generate_v1(client_with_refine_stub)
    response = client_with_refine_stub.post(
        "/users/alice/jobs/j1/letters/1/edit",
        json={"text": "Hello,\n\nShort.\n\nBest,\nX"},
    )
    assert response.status_code == 422
    assert "200" in response.json()["detail"] or "500" in response.json()["detail"]


def test_manual_edit_rejects_oversized_paragraph(
    client_with_refine_stub: TestClient,
) -> None:
    _generate_v1(client_with_refine_stub)
    big = "word " * 250
    response = client_with_refine_stub.post(
        "/users/alice/jobs/j1/letters/1/edit",
        json={"text": f"Header\n\nHello,\n\n{big}\n\nBest,\nX"},
    )
    assert response.status_code == 422
    assert "Paragraph" in response.json()["detail"]


def test_manual_edit_404_for_missing_source(
    client_with_refine_stub: TestClient,
) -> None:
    response = client_with_refine_stub.post(
        "/users/alice/jobs/j1/letters/99/edit",
        json={"text": _make_valid_edit_text()},
    )
    assert response.status_code == 404


def test_manual_edit_does_not_count_toward_refinement_cap(
    client_with_refine_stub: TestClient,
) -> None:
    """Saving 5 manual edits doesn't bump refinement_index, so refine
    after them still works (cap not yet hit)."""
    _generate_v1(client_with_refine_stub)
    for _ in range(5):
        client_with_refine_stub.post(
            "/users/alice/jobs/j1/letters/1/edit",
            json={"text": _make_valid_edit_text()},
        )

    # Refine should still succeed — refinement_index for v1 is still 0.
    response = client_with_refine_stub.post(
        "/users/alice/jobs/j1/letters/1/refine",
        json={"feedback": "Make it more technical"},
    )
    assert response.status_code == 202


# ----- "Why interested?" -----


def test_why_interested_returns_text_and_word_count(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _seed_resume(client)
    import role_tracker.api.routes.letters as letters_module

    monkeypatch.setattr(
        letters_module,
        "generate_why_interested",
        lambda **_: "Three sentences about why I want this role.",
    )
    response = client.post(
        "/users/alice/jobs/j1/why-interested",
        json={"target_words": 50},
    )
    assert response.status_code == 200
    body = response.json()
    assert "why I want this role" in body["text"]
    assert body["word_count"] == 8


def test_why_interested_404_when_job_unknown(
    client: TestClient,
) -> None:
    _seed_resume(client)
    response = client.post(
        "/users/alice/jobs/nonexistent/why-interested",
        json={"target_words": 50},
    )
    assert response.status_code == 404


def test_why_interested_400_when_no_resume(
    client: TestClient,
) -> None:
    response = client.post(
        "/users/alice/jobs/j1/why-interested",
        json={"target_words": 50},
    )
    assert response.status_code == 400
    assert "resume" in response.json()["detail"].lower()


def test_why_interested_validates_target_words(client: TestClient) -> None:
    _seed_resume(client)
    too_short = client.post(
        "/users/alice/jobs/j1/why-interested",
        json={"target_words": 5},
    )
    assert too_short.status_code == 422
    too_long = client.post(
        "/users/alice/jobs/j1/why-interested",
        json={"target_words": 500},
    )
    assert too_long.status_code == 422
