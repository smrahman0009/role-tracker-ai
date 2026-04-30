"""Jobs endpoints — see docs/api_spec.md §3.

Four routes:
- GET    /users/{user_id}/jobs                 list ranked jobs from cache
- POST   /users/{user_id}/jobs/refresh         async refresh from JSearch
- GET    /users/{user_id}/jobs/refresh/{id}    poll refresh status
- GET    /users/{user_id}/jobs/{job_id}        single-job detail

The refresh runs in a FastAPI BackgroundTask. The frontend polls the
refresh-status endpoint every 2-3 seconds; when status becomes "done"
or "failed", it stops polling. Stale-task sweep on every poll auto-fails
records stuck running for >5 minutes (handles App Service F1 sleep).
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

# We import these "via" the queries / resume routers to share the same
# default factories — that way tests overriding either also affect this
# router.
from role_tracker.api.routes.queries import get_query_store
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.api.schemas import (
    JobDetailResponse,
    JobFilter,
    JobListResponse,
    JobSummary,
    RefreshJobResponse,
    RefreshStatusResponse,
)
from role_tracker.applied.store import AppliedStore, FileAppliedStore
from role_tracker.config import Settings
from role_tracker.jobs.cache import (
    FileJobsCache,
    JobsCache,
    StoredScoredJob,
)
from role_tracker.jobs.filters import apply_list_filters
from role_tracker.jobs.jsearch import JSearchClient
from role_tracker.jobs.models import JobPosting
from role_tracker.jobs.pipeline import (
    MatchingResult,
    PipelineRunner,
    run_matching_pipeline,
)
from role_tracker.jobs.refresh_state import (
    FileRefreshTaskStore,
    RefreshTaskStore,
)
from role_tracker.matching.embeddings import Embedder
from role_tracker.matching.scorer import ScoredJob
from role_tracker.queries.base import QueryStore
from role_tracker.queries.models import SavedQuery
from role_tracker.resume.parser import parse_resume
from role_tracker.resume.store import ResumeStore
from role_tracker.users.yaml_store import YamlUserProfileStore

router = APIRouter(
    prefix="/users/{user_id}/jobs",
    tags=["jobs"],
)


def _user_top_n(user_id: str, *, default: int = 50) -> int:
    """Read the user's top_n_jobs preference, with a safe default."""
    try:
        return YamlUserProfileStore().get_user(user_id).top_n_jobs
    except FileNotFoundError:
        return default


# ----- Dependency factories -----


def get_jobs_cache() -> JobsCache:
    return FileJobsCache()


def get_refresh_store() -> RefreshTaskStore:
    return FileRefreshTaskStore()


def get_applied_store() -> AppliedStore:
    return FileAppliedStore()


def get_pipeline_runner() -> PipelineRunner:
    """Build the real pipeline (hits live JSearch + OpenAI). Tests override."""
    settings = Settings()
    embedder = Embedder(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )
    jsearch_client = JSearchClient(
        rapidapi_key=settings.jsearch_rapidapi_key,
        country="ca",
    )
    user_store = YamlUserProfileStore()

    def run(
        user_id: str, queries: list[SavedQuery], resume_text: str
    ) -> MatchingResult:
        # Pull exclusion lists + the user's top_n preference from the
        # YAML profile. Defaults if the user hasn't created one yet.
        top_n = 50
        try:
            user = user_store.get_user(user_id)
            exclude_companies = user.exclude_companies
            exclude_title_keywords = user.exclude_title_keywords
            exclude_publishers = user.exclude_publishers
            top_n = user.top_n_jobs
        except FileNotFoundError:
            exclude_companies = []
            exclude_title_keywords = []
            exclude_publishers = []

        cache_path = Path(f"data/resumes/{user_id}.embedding.json")
        return run_matching_pipeline(
            queries=queries,
            resume_text=resume_text,
            resume_embedding_cache_path=cache_path,
            embedder=embedder,
            jsearch_client=jsearch_client,
            exclude_companies=exclude_companies,
            exclude_title_keywords=exclude_title_keywords,
            exclude_publishers=exclude_publishers,
            limit_per_query=50,
            top_n=top_n,
        )

    return run


# ----- Routes -----


def _split_csv(value: str) -> list[str]:
    """Parse a comma-separated query param into a clean list."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


@router.get("", response_model=JobListResponse)
def list_jobs(
    user_id: str,
    filter: JobFilter = "unapplied",  # type: ignore[assignment]
    type: str = "",                     # comma-separated multi-value
    location: str = "",                 # comma-separated multi-value
    salary_min: int | None = None,
    hide_no_salary: bool = False,
    employment_types: str = "",         # comma-separated multi-value
    posted_within_days: int | None = None,
    cache: JobsCache = Depends(get_jobs_cache),
    applied_store: AppliedStore = Depends(get_applied_store),
) -> JobListResponse:
    """List ranked jobs from the latest cached snapshot, with applied flags
    and the inline filter-chip filters applied."""
    snapshot = cache.get_snapshot(user_id)
    if snapshot is None:
        return JobListResponse(
            jobs=[],
            total=0,
            total_unfiltered=0,
            hidden_by_filters=0,
            last_refreshed_at=None,
            candidates_seen=0,
            queries_run=0,
            top_n_cap=0,
        )

    applied_ids = applied_store.list_applied(user_id)
    all_jobs = [s.job for s in snapshot.jobs]
    score_by_id = {s.job.id: s.score for s in snapshot.jobs}
    total_unfiltered = len(all_jobs)

    # Step 1: applied/unapplied filter (the existing tabs).
    if filter == "applied":
        all_jobs = [j for j in all_jobs if j.id in applied_ids]
    elif filter == "unapplied":
        all_jobs = [j for j in all_jobs if j.id not in applied_ids]

    # Step 2: the inline filter-chip filters.
    filtered_jobs = apply_list_filters(
        all_jobs,
        type_terms=_split_csv(type),
        location_terms=_split_csv(location),
        salary_min=salary_min,
        hide_no_salary=hide_no_salary,
        employment_types=_split_csv(employment_types),
        posted_within_days=posted_within_days,
    )

    # Step 3: convert to summaries.
    summaries = [
        _to_summary_from_job(
            job,
            score=score_by_id.get(job.id, 0.0),
            applied=job.id in applied_ids,
        )
        for job in filtered_jobs
    ]

    return JobListResponse(
        jobs=summaries,
        total=len(summaries),
        total_unfiltered=total_unfiltered,
        hidden_by_filters=max(0, total_unfiltered - len(summaries)),
        last_refreshed_at=snapshot.last_refreshed_at,
        candidates_seen=snapshot.candidates_seen,
        queries_run=snapshot.queries_run,
        top_n_cap=snapshot.top_n_cap,
    )


@router.post(
    "/refresh",
    response_model=RefreshJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def refresh_jobs(
    user_id: str,
    background_tasks: BackgroundTasks,
    query_store: QueryStore = Depends(get_query_store),
    resume_store: ResumeStore = Depends(get_resume_store),
    cache: JobsCache = Depends(get_jobs_cache),
    refresh_store: RefreshTaskStore = Depends(get_refresh_store),
    pipeline: PipelineRunner = Depends(get_pipeline_runner),
) -> RefreshJobResponse:
    """Kick off a job-refresh as a background task. Returns immediately."""
    refresh_id = uuid.uuid4().hex[:12]
    refresh_store.create(user_id, refresh_id)
    background_tasks.add_task(
        _run_refresh_in_background,
        user_id=user_id,
        refresh_id=refresh_id,
        query_store=query_store,
        resume_store=resume_store,
        cache=cache,
        refresh_store=refresh_store,
        pipeline=pipeline,
    )
    return RefreshJobResponse(refresh_id=refresh_id, status="pending")


@router.get("/refresh/{refresh_id}", response_model=RefreshStatusResponse)
def get_refresh_status(
    user_id: str,
    refresh_id: str,
    refresh_store: RefreshTaskStore = Depends(get_refresh_store),
) -> RefreshStatusResponse:
    """Poll the status of an in-flight refresh."""
    record = refresh_store.get(user_id, refresh_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Refresh '{refresh_id}' not found for user '{user_id}'",
        )
    return RefreshStatusResponse(
        refresh_id=record.refresh_id,
        status=record.status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        jobs_added=record.jobs_added,
        candidates_seen=record.candidates_seen,
        queries_run=record.queries_run,
        error=record.error,
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job_detail(
    user_id: str,
    job_id: str,
    cache: JobsCache = Depends(get_jobs_cache),
    applied_store: AppliedStore = Depends(get_applied_store),
) -> JobDetailResponse:
    """Return one job's full details (including JD)."""
    snapshot = cache.get_snapshot(user_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No jobs cached. Refresh first.",
        )
    for stored in snapshot.jobs:
        if stored.job.id == job_id:
            return _to_detail(
                stored, applied=applied_store.is_applied(user_id, job_id)
            )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Job '{job_id}' not found in current snapshot",
    )


@router.post(
    "/{job_id}/applied",
    status_code=status.HTTP_204_NO_CONTENT,
)
def mark_applied(
    user_id: str,
    job_id: str,
    applied_store: AppliedStore = Depends(get_applied_store),
) -> Response:
    """Mark a job as applied — moves it to the 'Applied' filter."""
    if not applied_store.mark_applied(user_id, job_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job '{job_id}' is already marked applied",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{job_id}/applied",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unmark_applied(
    user_id: str,
    job_id: str,
    applied_store: AppliedStore = Depends(get_applied_store),
) -> Response:
    """Remove the applied flag — job returns to the 'Unapplied' list."""
    applied_store.unmark_applied(user_id, job_id)
    # Idempotent: returns 204 whether the job was applied or not.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- Helpers -----


def _to_summary(stored: StoredScoredJob, *, applied: bool = False) -> JobSummary:
    """Convert StoredScoredJob → JobSummary (no full description)."""
    return _to_summary_from_job(stored.job, score=stored.score, applied=applied)


def _to_summary_from_job(
    job: JobPosting, *, score: float, applied: bool = False
) -> JobSummary:
    """Build a JobSummary from a raw JobPosting + its match score."""
    desc = (job.description or "").strip()
    preview = desc[:240]
    if len(desc) > 240:
        # End at the last word boundary so we don't cut a word in half.
        last_space = preview.rfind(" ")
        if last_space > 200:
            preview = preview[:last_space]
        preview += "…"
    return JobSummary(
        job_id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        posted_at=job.posted_at,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        publisher=job.publisher,
        url=job.url,
        match_score=score,
        fit_assessment=None,    # populated when a letter is generated (later)
        applied=applied,
        description_preview=preview,
    )


def _to_detail(
    stored: StoredScoredJob, *, applied: bool = False
) -> JobDetailResponse:
    """Convert StoredScoredJob → JobDetailResponse (full description)."""
    return JobDetailResponse(
        job_id=stored.job.id,
        title=stored.job.title,
        company=stored.job.company,
        location=stored.job.location,
        posted_at=stored.job.posted_at,
        salary_min=stored.job.salary_min,
        salary_max=stored.job.salary_max,
        publisher=stored.job.publisher,
        url=stored.job.url,
        description=stored.job.description,
        match_score=stored.score,
        fit_assessment=None,
        applied=applied,
    )


def _run_refresh_in_background(
    *,
    user_id: str,
    refresh_id: str,
    query_store: QueryStore,
    resume_store: ResumeStore,
    cache: JobsCache,
    refresh_store: RefreshTaskStore,
    pipeline: PipelineRunner,
) -> None:
    """The actual refresh work. Runs after the 202 response is sent."""
    try:
        refresh_store.mark_running(user_id, refresh_id)

        queries = query_store.list_queries(user_id)
        if not queries:
            cache.save_snapshot(user_id, [])
            refresh_store.mark_done(user_id, refresh_id, jobs_added=0)
            return

        resume_bytes = resume_store.get_file_bytes(user_id)
        if resume_bytes is None:
            refresh_store.mark_failed(
                user_id,
                refresh_id,
                error="No resume uploaded. Upload one before refreshing.",
            )
            return

        # Parse the PDF via a temp file (pypdf wants a path).
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False
        ) as tmp:
            tmp.write(resume_bytes)
            tmp_path = Path(tmp.name)
        try:
            resume_text = parse_resume(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        result = pipeline(user_id, queries, resume_text)
        cache.save_snapshot(
            user_id,
            result.jobs,
            candidates_seen=result.candidates_seen,
            queries_run=result.queries_run,
            top_n_cap=_user_top_n(user_id),
        )
        refresh_store.mark_done(
            user_id,
            refresh_id,
            jobs_added=len(result.jobs),
            candidates_seen=result.candidates_seen,
            queries_run=result.queries_run,
        )

    except Exception as exc:  # noqa: BLE001
        refresh_store.mark_failed(user_id, refresh_id, error=str(exc))


# Re-export used by tests for dependency overrides.
__all__ = [
    "BaseModel",
    "get_jobs_cache",
    "get_pipeline_runner",
    "get_refresh_store",
    "router",
]
