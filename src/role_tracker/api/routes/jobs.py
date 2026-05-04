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
from datetime import UTC, datetime
from pathlib import Path

from anthropic import Anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

# We import these "via" the queries / resume routers to share the same
# default factories — that way tests overriding either also affect this
# router.
from role_tracker.api.routes.queries import get_query_store
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.api.schemas import (
    ApplicationListResponse,
    ApplicationSummary,
    FetchJobUrlRequest,
    FetchJobUrlResponse,
    JobDetailResponse,
    JobFilter,
    JobListResponse,
    JobSummary,
    ManualJobRequest,
    MarkAppliedRequest,
    RefreshJobResponse,
    RefreshStatusResponse,
    SearchJobsRequest,
    SearchJobsResponse,
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
from role_tracker.jobs.seen import FileSeenJobsStore, SeenJobsStore
from role_tracker.jobs.url_extract import (
    extract_job_from_url,
    refine_with_llm,
)
from role_tracker.letters.store import FileLetterStore, LetterStore
from role_tracker.matching.embeddings import Embedder
from role_tracker.matching.scorer import ScoredJob
from role_tracker.queries.base import QueryStore
from role_tracker.queries.models import SavedQuery
from role_tracker.resume.parser import parse_resume
from role_tracker.resume.store import ResumeStore
from role_tracker.usage import FileUsageStore, UsageRecorder, UsageStore
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
    """AppliedStore factory — picks DynamoDB when STORAGE_BACKEND=aws."""
    settings = Settings()
    if settings.storage_backend == "aws":
        from role_tracker.aws.dynamodb_applied_store import DynamoDBAppliedStore

        return DynamoDBAppliedStore(
            table_name=settings.ddb_applied_table,
            region_name=settings.aws_region,
        )
    return FileAppliedStore()


def get_seen_jobs_store() -> SeenJobsStore:
    """SeenJobsStore factory — picks DynamoDB when STORAGE_BACKEND=aws."""
    settings = Settings()
    if settings.storage_backend == "aws":
        from role_tracker.aws.dynamodb_seen_jobs_store import (
            DynamoDBSeenJobsStore,
        )

        return DynamoDBSeenJobsStore(
            table_name=settings.ddb_seen_jobs_table,
            region_name=settings.aws_region,
        )
    return FileSeenJobsStore()


def get_usage_store() -> UsageStore:
    """UsageStore factory.

    Picks the cloud-native (DynamoDB) backend when STORAGE_BACKEND=aws,
    otherwise falls back to the JSON-file store used in dev. Tests
    override this dependency at the FastAPI level.
    """
    settings = Settings()
    if settings.storage_backend == "aws":
        from role_tracker.aws.dynamodb_usage_store import DynamoDBUsageStore

        return DynamoDBUsageStore(
            table_name=settings.ddb_usage_table,
            region_name=settings.aws_region,
        )
    return FileUsageStore()


def get_letter_store_for_cleanup() -> LetterStore:
    """LetterStore factory — local copy to avoid a circular import on
    letters.py (which imports get_seen_jobs_store from this module).
    Tests override this to point at a tmp-rooted store."""
    settings = Settings()
    if settings.storage_backend == "aws":
        from role_tracker.aws.dynamodb_letter_store import DynamoDBLetterStore

        return DynamoDBLetterStore(
            table_name=settings.ddb_letters_table,
            region_name=settings.aws_region,
        )
    return FileLetterStore()


def get_extraction_anthropic_client() -> Anthropic:
    """Anthropic client used by the URL-extraction refine step. Mirrors
    letters' factory but kept local to avoid a circular import. Tests
    override with a stub."""
    settings = Settings()
    if not settings.anthropic_api_key:
        return Anthropic(api_key="placeholder")
    return Anthropic(api_key=settings.anthropic_api_key)


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
    usage_store = get_usage_store()

    def run(
        user_id: str,
        queries: list[SavedQuery],
        resume_text: str,
        *,
        limit_per_query: int = 50,
        top_n_override: int | None = None,
    ) -> MatchingResult:
        # Pull exclusion lists + the user's top_n preference from the
        # YAML profile. Defaults if the user hasn't created one yet.
        # `limit_per_query` is caller-controlled so the daily refresh
        # (50) and ad-hoc search (20) can use different JSearch budgets.
        # `top_n_override` lets ad-hoc searches choose a different cap
        # than the user's profile default.
        top_n = top_n_override if top_n_override is not None else 50
        try:
            user = user_store.get_user(user_id)
            exclude_companies = user.exclude_companies
            exclude_title_keywords = user.exclude_title_keywords
            exclude_publishers = user.exclude_publishers
            if top_n_override is None:
                top_n = user.top_n_jobs
        except FileNotFoundError:
            exclude_companies = []
            exclude_title_keywords = []
            exclude_publishers = []

        cache_path = Path(f"data/resumes/{user_id}.embedding.json")
        recorder = UsageRecorder(usage_store, user_id)
        return run_matching_pipeline(
            queries=queries,
            resume_text=resume_text,
            resume_embedding_cache_path=cache_path,
            embedder=embedder,
            jsearch_client=jsearch_client,
            exclude_companies=exclude_companies,
            exclude_title_keywords=exclude_title_keywords,
            exclude_publishers=exclude_publishers,
            limit_per_query=limit_per_query,
            top_n=top_n,
            usage_recorder=recorder,
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


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_jobs_snapshot(
    user_id: str,
    cache: JobsCache = Depends(get_jobs_cache),
) -> Response:
    """Clear the cached search snapshot.

    Only the snapshot is affected — applied records, letters, manual
    jobs, and seen_jobs all remain. The home page will show its empty
    state until the next search or refresh.
    """
    cache.clear_snapshot(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/applications", response_model=ApplicationListResponse)
def list_applications(
    user_id: str,
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    applied_store: AppliedStore = Depends(get_applied_store),
    resume_store: ResumeStore = Depends(get_resume_store),
) -> ApplicationListResponse:
    """List every job the user has marked as applied, with the rich
    record captured at apply time (applied_at, resume snapshot, letter
    version). Sorted by applied_at descending — most recent first."""
    applications = applied_store.list_applied(user_id)
    if not applications:
        return ApplicationListResponse(applications=[], total=0)

    current_resume = resume_store.get_metadata(user_id)
    current_sha = current_resume.sha256 if current_resume else ""

    items: list[ApplicationSummary] = []
    for job_id, record in applications.items():
        stored = seen_store.get(user_id, job_id)
        if stored is None:
            continue
        # "now replaced" tag: the user replaced their resume after
        # applying. Empty snapshot sha means the application predates
        # the snapshot feature — don't claim replacement in that case.
        replaced = bool(
            record.resume_sha256
            and current_sha
            and record.resume_sha256 != current_sha
        )
        items.append(
            ApplicationSummary(
                job=_to_summary_from_job(
                    stored.job, score=stored.score, applied=True
                ),
                applied_at=record.applied_at,
                resume_filename=record.resume_filename,
                resume_sha256=record.resume_sha256,
                letter_version_used=record.letter_version_used,
                resume_replaced_since=replaced,
            )
        )
    # Most recent first — applications without a timestamp (legacy
    # records) sort to the bottom.
    items.sort(
        key=lambda a: a.applied_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return ApplicationListResponse(applications=items, total=len(items))


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
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    pipeline: PipelineRunner = Depends(get_pipeline_runner),
) -> RefreshJobResponse:
    """Kick off a job-refresh as a background task. Returns immediately."""
    refresh_id = uuid.uuid4().hex[:12]
    refresh_store.create(user_id, refresh_id)
    background_tasks.add_task(
        _run_refresh_in_background,
        user_id=user_id,
        seen_store=seen_store,
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
    return _refresh_status_response(refresh_store, user_id, refresh_id)


# ----- Ad-hoc search (powers the home page) -----


@router.post(
    "/search",
    response_model=SearchJobsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def search_jobs(
    user_id: str,
    body: SearchJobsRequest,
    background_tasks: BackgroundTasks,
    resume_store: ResumeStore = Depends(get_resume_store),
    cache: JobsCache = Depends(get_jobs_cache),
    refresh_store: RefreshTaskStore = Depends(get_refresh_store),
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    pipeline: PipelineRunner = Depends(get_pipeline_runner),
) -> SearchJobsResponse:
    """Run an ad-hoc search using the supplied spec.

    Mirrors /jobs/refresh but takes a one-off query in the body instead
    of fanning out across saved searches. Uses a smaller per-query JSearch
    budget (limit_per_query=50, matching the refresh) so users don't burn
    their monthly quota on exploratory searches.
    """
    search_id = uuid.uuid4().hex[:12]
    refresh_store.create(user_id, search_id)
    background_tasks.add_task(
        _run_search_in_background,
        user_id=user_id,
        search_id=search_id,
        spec=body,
        resume_store=resume_store,
        cache=cache,
        refresh_store=refresh_store,
        seen_store=seen_store,
        pipeline=pipeline,
    )
    return SearchJobsResponse(search_id=search_id, status="pending")


@router.get("/search/{search_id}", response_model=RefreshStatusResponse)
def get_search_status(
    user_id: str,
    search_id: str,
    refresh_store: RefreshTaskStore = Depends(get_refresh_store),
) -> RefreshStatusResponse:
    """Poll the status of an in-flight search. Same lifecycle as refresh."""
    return _refresh_status_response(refresh_store, user_id, search_id)


def _refresh_status_response(
    refresh_store: RefreshTaskStore, user_id: str, task_id: str
) -> RefreshStatusResponse:
    record = refresh_store.get(user_id, task_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found for user '{user_id}'",
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


# ----- Manually-added jobs (URL paste / textbox flow) -----


@router.post("/manual/fetch", response_model=FetchJobUrlResponse)
def fetch_job_url(
    user_id: str,
    body: FetchJobUrlRequest,
    client: Anthropic = Depends(get_extraction_anthropic_client),
    usage_store: UsageStore = Depends(get_usage_store),
) -> FetchJobUrlResponse:
    """Best-effort extraction of title/company/JD from a URL.

    Two passes:
      1. Trafilatura grabs the JD body + page metadata (fast, free).
      2. If we got JD body text, send it to Claude Haiku to extract the
         actual hiring company and clean role title from the body. This
         handles recruiter / aggregator pages where the page metadata
         points to the publisher, not the actual employer.

    Always returns 200 — empty fields signal the extractor couldn't
    pull that piece. The frontend then asks the user to paste manually.
    """
    extracted = extract_job_from_url(body.url)
    title = extracted.title
    company = extracted.company
    location = ""
    description = extracted.description

    # LLM refinement is only worthwhile when we have description text.
    # Without a body, Haiku has nothing to read past the page metadata
    # we already have.
    if extracted.description:
        refined = refine_with_llm(
            description=extracted.description, client=client
        )
        UsageRecorder(usage_store, user_id).feature("url_extract_llm_refine")
        # Prefer LLM extraction over page metadata: the JD body knows
        # who's actually hiring, where the role is, and which paragraphs
        # are role-specific vs surrounding chrome.
        if refined["company"]:
            company = refined["company"]
        if refined["title"]:
            title = refined["title"]
        if refined["location"]:
            location = refined["location"]
        # Keep the cleaned description if the LLM produced one;
        # otherwise the raw Trafilatura text is better than nothing.
        if refined["description"]:
            description = refined["description"]

    return FetchJobUrlResponse(
        title=title,
        company=company,
        location=location,
        description=description,
    )


@router.post(
    "/manual",
    response_model=JobDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_job(
    user_id: str,
    body: ManualJobRequest,
    resume_store: ResumeStore = Depends(get_resume_store),
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    usage_store: UsageStore = Depends(get_usage_store),
) -> JobDetailResponse:
    """Save a manually-added job into seen_jobs.

    Embeds the JD against the user's resume so the match score is
    real (same as JSearch jobs). source="manual" tags it for the
    "My added jobs" filter. Detail/letter/Apply Kit flows then work
    unchanged because they all read from seen_jobs.
    """
    job_id = "manual:" + _hash_for_manual_job(
        url=body.url, title=body.title, company=body.company
    )
    posting = JobPosting(
        id=job_id,
        title=body.title.strip(),
        company=body.company.strip(),
        location=body.location.strip(),
        description=body.description.strip(),
        url=body.url.strip(),
        posted_at="",
        salary_min=body.salary_min,
        salary_max=body.salary_max,
        source="manual",
        publisher="",
        employment_type=body.employment_type.strip().upper(),
    )

    score = _score_manual_job(
        user_id, posting, resume_store, UsageRecorder(usage_store, user_id)
    )
    seen_store.upsert_many(user_id, [ScoredJob(job=posting, score=score)])

    return _to_detail(
        StoredScoredJob(job=posting, score=score), applied=False
    )


@router.get("/manual", response_model=JobListResponse)
def list_manual_jobs(
    user_id: str,
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    applied_store: AppliedStore = Depends(get_applied_store),
) -> JobListResponse:
    """Every job the user added manually, latest match-score first.

    Independent of search snapshots — manual jobs live forever in
    seen_jobs and are filtered by source=='manual' here.
    """
    applied_ids = applied_store.list_applied(user_id)
    all_seen = _all_seen_for_user(seen_store, user_id)
    manuals = [
        s for s in all_seen if s.job.source == "manual"
    ]
    summaries = [
        _to_summary_from_job(
            s.job, score=s.score, applied=s.job.id in applied_ids
        )
        for s in sorted(manuals, key=lambda s: s.score, reverse=True)
    ]
    return JobListResponse(
        jobs=summaries,
        total=len(summaries),
        total_unfiltered=len(summaries),
        hidden_by_filters=0,
        last_refreshed_at=None,
    )


@router.delete(
    "/manual/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_manual_job(
    user_id: str,
    job_id: str,
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    applied_store: AppliedStore = Depends(get_applied_store),
    letter_store: LetterStore = Depends(get_letter_store_for_cleanup),
) -> Response:
    """Delete a manually-added job and clean up its associated state.

    Scoped to manual jobs only (job_id starts with "manual:"). JSearch
    jobs rotate naturally with searches and shouldn't be deleted ad-hoc
    — refusing them keeps the user from accidentally nuking a result
    they were going to apply to in the next refresh cycle.

    Cleanup scope:
      - seen_jobs entry        (the job itself)
      - applied_store entry    (so it disappears from My Applications)
      - letter_store entries   (every saved version of any cover letter
                                generated for this job)
    """
    if not job_id.startswith("manual:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only manually-added jobs can be deleted. JSearch-sourced "
                "jobs rotate with search results."
            ),
        )
    if not seen_store.remove(user_id, job_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )
    applied_store.unmark_applied(user_id, job_id)
    letter_store.delete_all_versions(user_id, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _hash_for_manual_job(*, url: str, title: str, company: str) -> str:
    """Deterministic short id so re-adding the same posting overwrites
    instead of duplicating. Falls back on title+company when no URL."""
    import hashlib

    seed = (url or f"{title}|{company}").strip().lower()
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _score_manual_job(
    user_id: str,
    job: JobPosting,
    resume_store: ResumeStore,
    recorder: UsageRecorder,
) -> float:
    """Embed the JD against the user's resume and return cosine
    similarity. Returns 0.0 silently if anything goes wrong (no resume
    uploaded, embedding API down, etc.) — the user can still create the
    job, they just won't have a real score yet."""
    try:
        resume_bytes = resume_store.get_file_bytes(user_id)
        if resume_bytes is None:
            return 0.0
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resume_bytes)
            tmp_path = Path(tmp.name)
        try:
            resume_text = parse_resume(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        from role_tracker.matching.embeddings import (
            Embedder,
            load_or_embed_resume,
        )
        from role_tracker.matching.scorer import (
            cosine_similarity,
            job_to_embedding_text,
        )

        settings = Settings()
        embedder = Embedder(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
        )
        cache_path = Path(f"data/resumes/{user_id}.embedding.json")
        resume_vec = load_or_embed_resume(
            embedder,
            resume_text,
            cache_path,
            on_embed=lambda: recorder.feature("embedding"),
        )
        job_vec = embedder.embed([job_to_embedding_text(job)])[0]
        recorder.feature("embedding")
        return float(cosine_similarity(resume_vec, job_vec))
    except Exception:  # noqa: BLE001
        return 0.0


def _all_seen_for_user(
    seen_store: SeenJobsStore, user_id: str
) -> list[StoredScoredJob]:
    """Read the full seen_jobs index for a user."""
    return seen_store.list_all(user_id)


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job_detail(
    user_id: str,
    job_id: str,
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    applied_store: AppliedStore = Depends(get_applied_store),
) -> JobDetailResponse:
    """Return one job's full details (including JD).

    Reads from seen_jobs (the long-lived per-user index) so the detail
    page still works after a new search has rotated the current snapshot.
    """
    stored = seen_store.get(user_id, job_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )
    return _to_detail(stored, applied=applied_store.is_applied(user_id, job_id))


@router.post(
    "/{job_id}/applied",
    status_code=status.HTTP_204_NO_CONTENT,
)
def mark_applied(
    user_id: str,
    job_id: str,
    body: MarkAppliedRequest | None = None,
    applied_store: AppliedStore = Depends(get_applied_store),
    resume_store: ResumeStore = Depends(get_resume_store),
) -> Response:
    """Mark a job as applied. Captures an audit record: the timestamp,
    a snapshot of the resume metadata at apply time (filename + sha256),
    and the cover-letter version the user had selected (from body)."""
    resume_meta = resume_store.get_metadata(user_id)
    letter_version = body.letter_version_used if body else None

    if not applied_store.mark_applied(
        user_id,
        job_id,
        resume_filename=resume_meta.filename if resume_meta else "",
        resume_sha256=resume_meta.sha256 if resume_meta else "",
        letter_version_used=letter_version,
    ):
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
    seen_store: SeenJobsStore,
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
        # Persist into the long-lived index so detail / letter routes
        # still work after subsequent searches rotate the snapshot.
        seen_store.upsert_many(user_id, result.jobs)
        refresh_store.mark_done(
            user_id,
            refresh_id,
            jobs_added=len(result.jobs),
            candidates_seen=result.candidates_seen,
            queries_run=result.queries_run,
        )

    except Exception as exc:  # noqa: BLE001
        refresh_store.mark_failed(user_id, refresh_id, error=str(exc))


def _run_search_in_background(
    *,
    user_id: str,
    search_id: str,
    spec: SearchJobsRequest,
    resume_store: ResumeStore,
    cache: JobsCache,
    refresh_store: RefreshTaskStore,
    seen_store: SeenJobsStore,
    pipeline: PipelineRunner,
) -> None:
    """Ad-hoc search: build a one-off query from the spec and run the pipeline.

    Same lifecycle as a refresh; reuses RefreshTaskStore for status tracking.
    Uses limit_per_query=50 (5 JSearch pages per pair). The user has
    upgraded past the free tier so the conservative limit is no longer
    necessary; more candidates means better top-N ranking quality.
    """
    try:
        refresh_store.mark_running(user_id, search_id)

        resume_bytes = resume_store.get_file_bytes(user_id)
        if resume_bytes is None:
            refresh_store.mark_failed(
                user_id,
                search_id,
                error="No resume uploaded. Upload one before searching.",
            )
            return

        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False
        ) as tmp:
            tmp.write(resume_bytes)
            tmp_path = Path(tmp.name)
        try:
            resume_text = parse_resume(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        # Build one SavedQuery per `what` term — the pipeline already
        # handles multi-query fan-out, dedupe, and merge. Optional fields
        # (salary, employment, posted_within) are post-rank narrowers
        # surfaced via /jobs query params, not pipeline inputs — so they
        # don't affect the pipeline call here.
        terms = [t.strip() for t in spec.what if t.strip()]
        wheres = [w.strip() for w in spec.where if w.strip()]
        now = datetime.now(UTC)
        # Cartesian product: one SavedQuery per (what × where) pair.
        # The pipeline already dedupes by job_id across queries, so the
        # same job appearing for multiple terms only embeds once.
        ad_hoc_queries = [
            SavedQuery(
                query_id=f"search:{search_id}:{i}:{j}",
                what=term,
                where=where,
                enabled=True,
                created_at=now,
            )
            for i, term in enumerate(terms)
            for j, where in enumerate(wheres)
        ]

        result = pipeline(
            user_id,
            ad_hoc_queries,
            resume_text,
            limit_per_query=50,
            top_n_override=spec.top_n,
        )
        cache.save_snapshot(
            user_id,
            result.jobs,
            candidates_seen=result.candidates_seen,
            queries_run=result.queries_run,
            top_n_cap=spec.top_n if spec.top_n is not None else _user_top_n(user_id),
        )
        seen_store.upsert_many(user_id, result.jobs)
        refresh_store.mark_done(
            user_id,
            search_id,
            jobs_added=len(result.jobs),
            candidates_seen=result.candidates_seen,
            queries_run=result.queries_run,
        )

    except Exception as exc:  # noqa: BLE001
        refresh_store.mark_failed(user_id, search_id, error=str(exc))


# Re-export used by tests for dependency overrides.
__all__ = [
    "BaseModel",
    "get_jobs_cache",
    "get_pipeline_runner",
    "get_refresh_store",
    "get_seen_jobs_store",
    "router",
]
