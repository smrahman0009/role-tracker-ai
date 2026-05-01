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
    get_seen_jobs_store,
)
from role_tracker.api.routes.queries import get_query_store
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.applied.store import FileAppliedStore
from role_tracker.jobs.cache import FileJobsCache
from role_tracker.jobs.models import JobPosting
from role_tracker.jobs.refresh_state import FileRefreshTaskStore
from role_tracker.jobs.seen import FileSeenJobsStore
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


def _fake_pipeline_results() -> "MatchingResult":
    from role_tracker.jobs.pipeline import MatchingResult

    jobs = [
        ScoredJob(job=_job("j1", "Senior Data Scientist", "Shopify"), score=0.92),
        ScoredJob(job=_job("j2", "ML Engineer", "Stripe"), score=0.81),
    ]
    return MatchingResult(jobs=jobs, candidates_seen=len(jobs), queries_run=1)


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
    app.dependency_overrides[get_seen_jobs_store] = lambda: FileSeenJobsStore(
        root=tmp_path / "seen"
    )
    app.dependency_overrides[get_pipeline_runner] = (
        lambda: lambda _user_id, _queries, _resume, **_: _fake_pipeline_results()
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


# ----- inline filter chips on GET /jobs -----


def test_list_response_reports_unfiltered_total_and_hidden_count(
    client: TestClient,
) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    # Mock pipeline returns 2 ScoredJobs (j1 = Senior Data Scientist,
    # j2 = ML Engineer). Filter by type=data — j1 matches, j2 doesn't.
    response = client.get("/users/alice/jobs?filter=all&type=data")
    body = response.json()
    assert body["total"] == 1
    assert body["total_unfiltered"] == 2
    assert body["hidden_by_filters"] == 1
    assert body["jobs"][0]["job_id"] == "j1"


def test_type_filter_multi_value_or_logic(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    response = client.get(
        "/users/alice/jobs?filter=all&type=data%20scientist,ml%20engineer"
    )
    body = response.json()
    # Both fixture jobs match.
    assert body["total"] == 2


def test_location_filter(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    # Both fixture jobs are in Toronto, so this matches both.
    body = client.get("/users/alice/jobs?filter=all&location=toronto").json()
    assert body["total"] == 2

    # Filter that matches none.
    body = client.get("/users/alice/jobs?filter=all&location=halifax").json()
    assert body["total"] == 0
    assert body["hidden_by_filters"] == 2


def test_filters_combine_with_applied_filter(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    # Mark j1 applied, then filter by type=ml — j2 is the only ML role
    # AND it's unapplied, so the unapplied+type filter returns just j2.
    client.post("/users/alice/jobs/j1/applied")
    body = client.get("/users/alice/jobs?filter=unapplied&type=ml").json()
    assert body["total"] == 1
    assert body["jobs"][0]["job_id"] == "j2"


def test_no_filters_returns_everything(client: TestClient) -> None:
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")

    body = client.get("/users/alice/jobs?filter=all").json()
    assert body["total"] == 2
    assert body["total_unfiltered"] == 2
    assert body["hidden_by_filters"] == 0


def test_filters_on_empty_snapshot(client: TestClient) -> None:
    """Filtering on a missing snapshot should return zeros, not 500."""
    body = client.get(
        "/users/alice/jobs?type=data&salary_min=80000"
    ).json()
    assert body["total"] == 0
    assert body["total_unfiltered"] == 0
    assert body["hidden_by_filters"] == 0


# ----- ad-hoc search -----


def test_search_returns_202_and_id(client: TestClient) -> None:
    _seed_resume(client)
    response = client.post(
        "/users/alice/jobs/search",
        json={"what": ["data scientist"], "where": ["Halifax"]},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["search_id"]


def test_search_writes_results_to_snapshot_and_seen_store(
    client: TestClient,
) -> None:
    _seed_resume(client)
    search_response = client.post(
        "/users/alice/jobs/search",
        json={"what": ["data scientist"], "where": ["Halifax"]},
    )
    search_id = search_response.json()["search_id"]

    # Background task ran synchronously after the response in TestClient.
    poll = client.get(f"/users/alice/jobs/search/{search_id}").json()
    assert poll["status"] == "done"
    assert poll["jobs_added"] == 2

    # Results visible via the regular /jobs endpoint.
    listed = client.get("/users/alice/jobs?filter=all").json()
    assert listed["total"] == 2

    # And the seen_store is populated so detail/letter routes will work.
    detail = client.get("/users/alice/jobs/j1")
    assert detail.status_code == 200


def test_search_fails_without_resume(client: TestClient) -> None:
    response = client.post(
        "/users/alice/jobs/search",
        json={"what": ["data scientist"], "where": ["Halifax"]},
    )
    search_id = response.json()["search_id"]
    poll = client.get(f"/users/alice/jobs/search/{search_id}").json()
    assert poll["status"] == "failed"
    assert "resume" in poll["error"].lower()


def test_search_validates_required_fields(client: TestClient) -> None:
    _seed_resume(client)
    response = client.post(
        "/users/alice/jobs/search", json={"what": [], "where": ["Halifax"]}
    )
    assert response.status_code == 422


def test_search_status_404_for_unknown_id(client: TestClient) -> None:
    response = client.get("/users/alice/jobs/search/nonexistent")
    assert response.status_code == 404


def test_search_accepts_multiple_what_terms(client: TestClient) -> None:
    """The pipeline fans out across each `what` term and merges results."""
    _seed_resume(client)
    response = client.post(
        "/users/alice/jobs/search",
        json={
            "what": ["machine learning engineer", "data scientist"],
            "where": ["Halifax, Canada"],
        },
    )
    assert response.status_code == 202


def test_search_rejects_more_than_three_what_terms(client: TestClient) -> None:
    """Cap is 3 to keep the JSearch quota cost bounded."""
    _seed_resume(client)
    response = client.post(
        "/users/alice/jobs/search",
        json={
            "what": ["one", "two", "three", "four"],
            "where": ["Halifax"],
        },
    )
    assert response.status_code == 422


def test_search_accepts_top_n_override(client: TestClient) -> None:
    """`top_n` in the body overrides the user's profile default."""
    _seed_resume(client)
    response = client.post(
        "/users/alice/jobs/search",
        json={"what": ["data scientist"], "where": ["Halifax"], "top_n": 25},
    )
    assert response.status_code == 202


def test_search_rejects_top_n_out_of_range(client: TestClient) -> None:
    _seed_resume(client)
    response = client.post(
        "/users/alice/jobs/search",
        json={"what": ["data scientist"], "where": ["Halifax"], "top_n": 999},
    )
    assert response.status_code == 422


# ----- /applications -----


def test_applications_empty_when_nothing_applied(client: TestClient) -> None:
    body = client.get("/users/alice/jobs/applications").json()
    assert body["jobs"] == []
    assert body["total"] == 0


def test_applications_returns_applied_from_seen_store(
    client: TestClient,
) -> None:
    """Apply a job from a search; it should show up in /applications."""
    _seed_resume(client)
    _seed_query(client)
    refresh_response = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh_response.json()['refresh_id']}")
    client.post("/users/alice/jobs/j1/applied")

    body = client.get("/users/alice/jobs/applications").json()
    assert body["total"] == 1
    assert body["jobs"][0]["job_id"] == "j1"
    assert body["jobs"][0]["applied"] is True


def test_applications_survives_snapshot_rotation(client: TestClient) -> None:
    """Applied jobs stay reachable even after a new search clobbers the snapshot.

    This is the whole point of the seen_jobs index — applications shouldn't
    disappear because the user ran another search.
    """
    _seed_resume(client)
    _seed_query(client)
    # First refresh: cache j1 + j2, apply j1.
    r1 = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{r1.json()['refresh_id']}")
    client.post("/users/alice/jobs/j1/applied")

    # Run an ad-hoc search — same fake pipeline returns j1 + j2 again, but
    # in real life this would rotate the snapshot to a new set of jobs.
    s = client.post(
        "/users/alice/jobs/search",
        json={"what": ["data scientist"], "where": ["Halifax"]},
    )
    client.get(f"/users/alice/jobs/search/{s.json()['search_id']}")

    # j1 is still in /applications regardless of what's in the snapshot now.
    body = client.get("/users/alice/jobs/applications").json()
    assert body["total"] == 1
    assert body["jobs"][0]["job_id"] == "j1"


def test_search_accepts_multi_value_where(client: TestClient) -> None:
    """Multiple cities in `where`; pipeline runs cartesian × queries."""
    _seed_resume(client)
    response = client.post(
        "/users/alice/jobs/search",
        json={
            "what": ["data scientist"],
            "where": ["Halifax", "Montreal", "Toronto"],
        },
    )
    assert response.status_code == 202


def test_search_rejects_more_than_three_wheres(client: TestClient) -> None:
    """Same 3-cap as `what`, for the same JSearch-quota reason."""
    _seed_resume(client)
    response = client.post(
        "/users/alice/jobs/search",
        json={
            "what": ["data scientist"],
            "where": ["A", "B", "C", "D"],
        },
    )
    assert response.status_code == 422


def test_search_rejects_empty_where_list(client: TestClient) -> None:
    _seed_resume(client)
    response = client.post(
        "/users/alice/jobs/search",
        json={"what": ["data scientist"], "where": []},
    )
    assert response.status_code == 422


# ----- manually-added jobs -----


def test_create_manual_job_returns_201_and_detail(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """User pastes a JD; backend stores it in seen_jobs with source=manual
    and returns the detail shape so the frontend can navigate."""
    _seed_resume(client)
    # Don't actually call OpenAI for embedding — the score path is
    # caught by a broad except and returns 0.0, which is fine.
    response = client.post(
        "/users/alice/jobs/manual",
        json={
            "title": "Senior ML Engineer",
            "company": "Acme Corp",
            "description": (
                "We're hiring an ML engineer to build production "
                "recommendation systems. You'll own model training, "
                "deployment, and monitoring. 5+ years experience."
            ),
            "location": "Halifax, NS",
            "url": "https://acme.example.com/jobs/123",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Senior ML Engineer"
    assert body["company"] == "Acme Corp"
    assert body["job_id"].startswith("manual:")


def test_create_manual_job_persists_to_seen_jobs(client: TestClient) -> None:
    """Subsequent GET /jobs/{id} should find the manual job."""
    _seed_resume(client)
    create = client.post(
        "/users/alice/jobs/manual",
        json={
            "title": "Senior ML Engineer",
            "company": "Acme",
            "description": "Build production ML systems. 5+ years experience required.",
        },
    )
    job_id = create.json()["job_id"]
    detail = client.get(f"/users/alice/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Senior ML Engineer"


def test_create_manual_job_rejects_short_description(client: TestClient) -> None:
    response = client.post(
        "/users/alice/jobs/manual",
        json={
            "title": "ML Engineer",
            "company": "Acme",
            "description": "too short",
        },
    )
    assert response.status_code == 422


def test_create_manual_job_dedupes_by_url(client: TestClient) -> None:
    """Re-adding the same URL should overwrite the prior entry, not
    create a duplicate (deterministic id from url hash)."""
    _seed_resume(client)
    body = {
        "title": "ML Engineer",
        "company": "Acme",
        "description": "Build production ML systems for recommendations team.",
        "url": "https://acme.example.com/jobs/123",
    }
    first = client.post("/users/alice/jobs/manual", json=body).json()
    second = client.post("/users/alice/jobs/manual", json=body).json()
    assert first["job_id"] == second["job_id"]


def test_list_manual_jobs_empty(client: TestClient) -> None:
    body = client.get("/users/alice/jobs/manual").json()
    assert body["jobs"] == []
    assert body["total"] == 0


def test_list_manual_jobs_returns_only_manual_source(
    client: TestClient,
) -> None:
    """seen_jobs may contain JSearch-sourced jobs (from refresh) too;
    the manual list filters by source='manual'."""
    _seed_resume(client)
    _seed_query(client)
    # Seed 2 jsearch jobs via refresh.
    refresh = client.post("/users/alice/jobs/refresh")
    client.get(f"/users/alice/jobs/refresh/{refresh.json()['refresh_id']}")
    # Add 1 manual job.
    client.post(
        "/users/alice/jobs/manual",
        json={
            "title": "Custom Role",
            "company": "Acme",
            "description": (
                "Job description for the manual-add flow test. "
                "Build production ML systems for the recommendations team."
            ),
        },
    )
    body = client.get("/users/alice/jobs/manual").json()
    assert body["total"] == 1
    assert body["jobs"][0]["title"] == "Custom Role"


def test_fetch_job_url_returns_empty_on_unreachable(
    client: TestClient,
) -> None:
    """The fetch helper never raises — bad URLs just return empty fields
    so the frontend can fall back to manual paste."""
    response = client.post(
        "/users/alice/jobs/manual/fetch",
        json={"url": "https://this-does-not-resolve-12345.invalid/job"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["description"] == ""


def test_fetch_job_url_validates_min_length(client: TestClient) -> None:
    response = client.post(
        "/users/alice/jobs/manual/fetch",
        json={"url": "x"},
    )
    assert response.status_code == 422
