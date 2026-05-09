"""Tests for POST /users/{id}/jobs/{job_id}/cover-letter/analysis."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from role_tracker.api.main import create_app
from role_tracker.api.routes.jobs import (
    get_seen_jobs_store,
    get_usage_store,
)
from role_tracker.api.routes.letters import get_anthropic_client
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.jobs.models import JobPosting
from role_tracker.jobs.seen import FileSeenJobsStore
from role_tracker.matching.scorer import ScoredJob
from role_tracker.resume.store import FileResumeStore
from role_tracker.usage import FileUsageStore

_VALID_PAYLOAD = {
    "strong": [
        "Python, 5 yrs (JD asks 3+)",
        "LLM agent loops shipped to prod",
    ],
    "gaps": ["Kubernetes (resume shows Docker only)"],
    "partial": ["Distributed systems, 1 yr"],
    "excitement_hooks": ["their focus on real-time inference"],
}


# ----- stub Anthropic client ------------------------------------------------


class _TextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)]


class _Messages:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def create(self, **_kwargs: Any) -> _Response:
        if isinstance(self._payload, str):
            return _Response(self._payload)
        return _Response(json.dumps(self._payload))


class _StubAnthropic:
    def __init__(self, payload: object) -> None:
        self.messages = _Messages(payload)


# ----- helpers --------------------------------------------------------------


def _job(job_id: str = "j1") -> JobPosting:
    return JobPosting(
        id=job_id,
        title="Senior Data Scientist",
        company="Shopify",
        location="Toronto",
        description=(
            "We're hiring a senior DS to ship LLM-powered features. "
            "5+ years Python, experience with agentic systems, "
            "Kubernetes a plus."
        ),
        url="https://example.com",
        posted_at="2026-04-28T00:00:00Z",
        source="jsearch",
        publisher="Shopify Careers",
    )


def _make_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    anthropic_payload: object = _VALID_PAYLOAD,
    *,
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
        resume_store.save_resume(
            "alice", content=b"%PDF-fake", filename="alice.pdf"
        )

    usage_store = FileUsageStore(root=tmp_path / "usage")

    app.dependency_overrides[get_resume_store] = lambda: resume_store
    app.dependency_overrides[get_seen_jobs_store] = lambda: seen_store
    app.dependency_overrides[get_usage_store] = lambda: usage_store
    app.dependency_overrides[get_anthropic_client] = lambda: _StubAnthropic(
        anthropic_payload
    )

    return TestClient(app)


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    with _make_client(monkeypatch, tmp_path) as c:
        yield c


# ----- happy path -----------------------------------------------------------


def test_analysis_returns_four_lists(client: TestClient) -> None:
    response = client.post("/users/alice/jobs/j1/cover-letter/analysis", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["strong"] == _VALID_PAYLOAD["strong"]
    assert body["gaps"] == _VALID_PAYLOAD["gaps"]
    assert body["partial"] == _VALID_PAYLOAD["partial"]
    assert body["excitement_hooks"] == _VALID_PAYLOAD["excitement_hooks"]
    # Default model is now Sonnet (was Haiku pre-restoration); the
    # panel exposes a toggle so users can downgrade per call.
    assert body["model"].startswith("claude-sonnet-")


def test_analysis_records_usage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Each successful call should tick the cover_letter_analysis counter."""
    with _make_client(monkeypatch, tmp_path) as client:
        response = client.post("/users/alice/jobs/j1/cover-letter/analysis", json={})
        assert response.status_code == 200

        usage_response = client.get("/users/alice/usage")
        usage = usage_response.json()
        feature_calls = {f["feature"]: f["count"] for f in usage["current"]["feature_calls"]}
        assert feature_calls.get("cover_letter_analysis") == 1


# ----- error paths ----------------------------------------------------------


def test_analysis_404_when_job_unknown(client: TestClient) -> None:
    response = client.post(
        "/users/alice/jobs/missing/cover-letter/analysis", json={}
    )
    assert response.status_code == 404


def test_analysis_400_when_resume_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with _make_client(monkeypatch, tmp_path, seed_resume=False) as client:
        response = client.post("/users/alice/jobs/j1/cover-letter/analysis", json={})
        assert response.status_code == 400
        assert "resume" in response.json()["detail"].lower()


def test_analysis_502_when_model_returns_garbage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If the model returns non-JSON we surface a 502 rather than 500."""
    with _make_client(
        monkeypatch, tmp_path, anthropic_payload="this is prose not json"
    ) as client:
        response = client.post("/users/alice/jobs/j1/cover-letter/analysis", json={})
        assert response.status_code == 502
        assert "json" in response.json()["detail"].lower()


def test_analysis_honours_haiku_model_choice(client: TestClient) -> None:
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/analysis",
        json={"model": "haiku"},
    )
    assert response.status_code == 200
    assert response.json()["model"].startswith("claude-haiku-")


def test_analysis_rejects_invalid_model_alias(client: TestClient) -> None:
    response = client.post(
        "/users/alice/jobs/j1/cover-letter/analysis",
        json={"model": "opus"},
    )
    assert response.status_code == 422
