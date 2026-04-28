"""Tests for the jobs API routes.

The pipeline runner is mocked — no real JSearch / OpenAI calls happen
in these tests. The mock produces deterministic ScoredJobs so we can
verify the full route + background-task flow end to end.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from role_tracker.api.main import create_app
from role_tracker.api.routes.jobs import (
    get_applied_store,
    get_jobs_cache,
    get_pipeline_runner,
    get_refresh_store,
)
from role_tracker.api.routes.queries import get_query_store
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.applied.store import FileAppliedStore
from role_tracker.jobs.cache import FileJobsCache
from role_tracker.jobs.models import JobPosting
from role_tracker.jobs.refresh_state import FileRefreshTaskStore
from role_tracker.matching.scorer import ScoredJob
from role_tracker.queries.json_store import JsonQueryStore
from role_tracker.resume.store import FileResumeStore

_FAKE_PDF = b"%PDF-1.4\n% fake\n%%EOF\n"


def _job(job_id: str, title: str, company: str) -> JobPosting:
    return JobPosting(
        id=job_id,
        title=title,
        company=company,
        location="Toronto",
        description=(
            "Build ML models. " * 50  # ~1000 chars to test preview
        ),
        url=f"https://example.com/{job_id}",
        posted_at="2026-04-28T00:00:00Z",
        source="jsearch",
        publisher=f"{company} Careers",
    )


def _fake_pipeline_results() -> list[ScoredJob]:
    return [
        ScoredJob(job=_job("j1", "Senior Data Scientist", "Shopify"), score=0.92),
        ScoredJob(job=_job("j2", "ML Engineer", "Stripe"), score=0.81),
    ]


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    """Test client with all stores rooted in tmp_path, pipeline mocked."""
    monkeypatch.delenv("APP_TOKEN", raising=False)

    # Patch the resume parser so the mock PDF doesn't have to be real.
    import role_tracker.api.routes.jobs as jobs_module

    monkeypatch.setattr(jobs_module, "parse_resume", lambda _: "fake resume text")

    app = create_app()
    app.dependency_overrides[get_query_store] = lambda: JsonQueryStore(
        root=tmp_path / "queries", bootstrap_yaml_root=tmp_path / "users"
    )
    app.dependency_overrides[get_resume_store] = lambda: FileResumeStore(
        root=tmp_path / "resumes"
    )
    app.dependency_overrides[get_jobs_cache] = lambda: FileJobsCache(
        root=tmp_path / "jobs"
    )
    app.dependency_overrides[get_refresh_store] = lambda: FileRefreshTaskStore(
        root=tmp_path / "jobs"
    )
    app.dependency_overrides[get_applied_store] = lambda: FileAppliedStore(
        root=tmp_path / "applied"
    )
    app.dependency_overrides[get_pipeline_runner] = (
        lambda: lambda _user_id, _queries, _resume: _fake_pipeline_results()
    )

    with TestClient(app) as c:
        yield c


def _seed_resume(client: TestClient, user_id: str = "alice") -> None:
    client.post(
        f"/users/{user_id}/resume",
        files={"file": ("r.pdf", _FAKE_PDF, "application/pdf")},
    )


def _seed_query(client: TestClient, user_id: str = "alice") -> None:
    client.post(
        f"/users/{user_id}/queries",
        json={"what": "data scientist", "where": "canada"},
    )


# ----- list -----


def test_list_empty_when_no_snapshot(client: TestClient) -> None:
    response = client.get("/users/alice/jobs")
    assert response.status_code == 200
    body = response.json()
    assert body["jobs"] == []
    assert body["total"] == 0
    assert body["last_refreshed_at"] is None


def test_list_filter_unapplied_returns_all_when_none_applied(
    client: TestClient,
) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    refresh_id = refresh_response.json()["refresh_id"]

    # Run the BackgroundTask synchronously (TestClient does this).
    # Wait for it to settle, then poll.
    poll = client.get(f"/users/alice/jobs/refresh/{refresh_id}")
    assert poll.json()["status"] == "done"

    response = client.get("/users/alice/jobs?filter=unapplied")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["jobs"][0]["match_score"] == 0.92


def test_list_filter_applied_returns_only_marked(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    # Initially no jobs are marked applied.
    assert client.get("/users/alice/jobs?filter=applied").json()["jobs"] == []

    # Mark one job applied; it should now appear in 'applied', not 'unapplied'.
    client.post("/users/alice/jobs/j1/applied")
    applied = client.get("/users/alice/jobs?filter=applied").json()
    unapplied = client.get("/users/alice/jobs?filter=unapplied").json()
    assert len(applied["jobs"]) == 1
    assert applied["jobs"][0]["job_id"] == "j1"
    assert applied["jobs"][0]["applied"] is True
    assert {j["job_id"] for j in unapplied["jobs"]} == {"j2"}


def test_list_filter_all_includes_both(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")
    client.post("/users/alice/jobs/j1/applied")

    response = client.get("/users/alice/jobs?filter=all")
    assert response.json()["total"] == 2


def test_list_includes_description_preview(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    response = client.get("/users/alice/jobs")
    summary = response.json()["jobs"][0]
    assert "description_preview" in summary
    assert len(summary["description_preview"]) <= 245  # 240 + ellipsis
    assert summary["description_preview"].endswith("…")


# ----- refresh -----


def test_refresh_returns_202_and_id(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    response = client.post("/users/alice/jobs/refresh")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["refresh_id"]


def test_refresh_completes_and_caches_jobs(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    refresh_id = refresh_response.json()["refresh_id"]

    poll = client.get(f"/users/alice/jobs/refresh/{refresh_id}")
    body = poll.json()
    assert body["status"] == "done"
    assert body["jobs_added"] == 2
    assert body["completed_at"] is not None


def test_refresh_fails_without_resume(client: TestClient) -> None:
    _seed_query(client)  # has queries but no resume
    refresh_response = client.post("/users/alice/jobs/refresh")
    refresh_id = refresh_response.json()["refresh_id"]

    poll = client.get(f"/users/alice/jobs/refresh/{refresh_id}")
    body = poll.json()
    assert body["status"] == "failed"
    assert "resume" in body["error"].lower()


def test_refresh_with_no_queries_completes_with_zero(client: TestClient) -> None:
    _seed_resume(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    refresh_id = refresh_response.json()["refresh_id"]

    poll = client.get(f"/users/alice/jobs/refresh/{refresh_id}")
    body = poll.json()
    assert body["status"] == "done"
    assert body["jobs_added"] == 0


# ----- poll -----


def test_poll_404_for_unknown_refresh(client: TestClient) -> None:
    response = client.get("/users/alice/jobs/refresh/nonexistent")
    assert response.status_code == 404


# ----- detail -----


def test_detail_404_when_no_snapshot(client: TestClient) -> None:
    response = client.get("/users/alice/jobs/anything")
    assert response.status_code == 404


def test_detail_returns_full_description(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    response = client.get("/users/alice/jobs/j1")
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "j1"
    assert body["title"] == "Senior Data Scientist"
    assert "Build ML models" in body["description"]
    # Detail endpoint returns the full description, not a preview.
    assert len(body["description"]) > 240


def test_detail_404_for_missing_job(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    response = client.get("/users/alice/jobs/nonexistent")
    assert response.status_code == 404


def test_detail_reflects_applied_flag(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    pre = client.get("/users/alice/jobs/j1").json()
    assert pre["applied"] is False

    client.post("/users/alice/jobs/j1/applied")
    post = client.get("/users/alice/jobs/j1").json()
    assert post["applied"] is True


# ----- apply / unapply -----


def test_mark_applied_returns_204(client: TestClient) -> None:
    response = client.post("/users/alice/jobs/j1/applied")
    assert response.status_code == 204


def test_mark_applied_409_when_already_applied(client: TestClient) -> None:
    client.post("/users/alice/jobs/j1/applied")
    response = client.post("/users/alice/jobs/j1/applied")
    assert response.status_code == 409


def test_unmark_applied_returns_204(client: TestClient) -> None:
    client.post("/users/alice/jobs/j1/applied")
    response = client.delete("/users/alice/jobs/j1/applied")
    assert response.status_code == 204


def test_unmark_applied_idempotent_when_not_applied(client: TestClient) -> None:
    """DELETE on a non-applied job is fine — returns 204, not 404."""
    response = client.delete("/users/alice/jobs/never_applied/applied")
    assert response.status_code == 204


def test_apply_unapply_roundtrip(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    client.post("/users/alice/jobs/j1/applied")
    assert client.get("/users/alice/jobs/j1").json()["applied"] is True

    client.delete("/users/alice/jobs/j1/applied")
    assert client.get("/users/alice/jobs/j1").json()["applied"] is False
