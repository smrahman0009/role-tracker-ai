"""Cover letter endpoints — see docs/api_spec.md §4.

This is where the Phase 4 agent (commit_to_strategy → critique → save loop)
gets exposed over HTTP. Generation runs as a background task; the frontend
polls the letter-jobs endpoint until status="done", then fetches the
saved letter.

Six endpoints:
- POST   /users/{user_id}/jobs/{job_id}/letters
        Kick off generation (async). Returns generation_id (202).
- GET    /users/{user_id}/letter-jobs/{generation_id}
        Poll status. When done, includes the full Letter.
- GET    /users/{user_id}/jobs/{job_id}/letters
        List all saved versions for a job (latest first).
- GET    /users/{user_id}/jobs/{job_id}/letters/{version}
        Get one specific version's content + strategy + critique.
- GET    /users/{user_id}/jobs/{job_id}/letters/{version}/download.md
        Download the letter as raw Markdown.
- POST   /users/{user_id}/jobs/{job_id}/regenerate
        Same as generate — explicit endpoint for "throw away strategy
        and start over". Same input shape, same response shape.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from anthropic import Anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import Response

from role_tracker.api.routes.jobs import get_jobs_cache
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.api.schemas import (
    CritiqueScore,
    GenerateLetterRequest,
    GenerateLetterResponse,
    Letter,
    LetterGenerationStatus,
    LetterVersionList,
    Strategy,
)
from role_tracker.config import Settings
from role_tracker.cover_letter.agent import generate_cover_letter_agent
from role_tracker.jobs.cache import JobsCache
from role_tracker.jobs.models import JobPosting
from role_tracker.letters.generation_state import (
    FileLetterGenerationStore,
    LetterGenerationStore,
)
from role_tracker.letters.models import StoredLetter
from role_tracker.letters.store import FileLetterStore, LetterStore
from role_tracker.resume.parser import parse_resume
from role_tracker.resume.store import ResumeStore
from role_tracker.users.base import UserProfileStore
from role_tracker.users.yaml_store import YamlUserProfileStore

router = APIRouter(tags=["letters"])


# ----- Dependencies -----


def get_letter_store() -> LetterStore:
    return FileLetterStore()


def get_letter_generation_store() -> LetterGenerationStore:
    return FileLetterGenerationStore()


def get_user_profile_store() -> UserProfileStore:
    """Tests override this with a stub or a tmp-rooted YAML store."""
    return YamlUserProfileStore()


def get_anthropic_client() -> Anthropic:
    """Anthropic SDK client. Tests override with a stub."""
    settings = Settings()
    if not settings.anthropic_api_key:
        # Don't raise here — let the route raise with a clearer error if
        # someone actually tries to generate.
        return Anthropic(api_key="placeholder")
    return Anthropic(api_key=settings.anthropic_api_key)


# ----- Routes -----


@router.post(
    "/users/{user_id}/jobs/{job_id}/letters",
    response_model=GenerateLetterResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_letter(
    user_id: str,
    job_id: str,
    body: GenerateLetterRequest,  # noqa: ARG001 — reserved for future fields
    background_tasks: BackgroundTasks,
    cache: JobsCache = Depends(get_jobs_cache),
    resume_store: ResumeStore = Depends(get_resume_store),
    letter_store: LetterStore = Depends(get_letter_store),
    generation_store: LetterGenerationStore = Depends(get_letter_generation_store),
    user_store: UserProfileStore = Depends(get_user_profile_store),
    client: Anthropic = Depends(get_anthropic_client),
) -> GenerateLetterResponse:
    """Kick off a cover-letter generation. Returns immediately."""
    return _start_generation(
        user_id=user_id,
        job_id=job_id,
        background_tasks=background_tasks,
        cache=cache,
        resume_store=resume_store,
        letter_store=letter_store,
        generation_store=generation_store,
        user_store=user_store,
        client=client,
    )


@router.post(
    "/users/{user_id}/jobs/{job_id}/regenerate",
    response_model=GenerateLetterResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def regenerate_letter(
    user_id: str,
    job_id: str,
    background_tasks: BackgroundTasks,
    cache: JobsCache = Depends(get_jobs_cache),
    resume_store: ResumeStore = Depends(get_resume_store),
    letter_store: LetterStore = Depends(get_letter_store),
    generation_store: LetterGenerationStore = Depends(get_letter_generation_store),
    user_store: UserProfileStore = Depends(get_user_profile_store),
    client: Anthropic = Depends(get_anthropic_client),
) -> GenerateLetterResponse:
    """Throw away the existing strategy and start over.

    Implementation note: this is the same code path as generate. The agent
    always commits a fresh strategy on every run, so 'throwing away' is
    automatic — we just kick off a new generation. The two endpoints exist
    as separate paths because the user's mental model differs even if the
    backend behavior doesn't.
    """
    return _start_generation(
        user_id=user_id,
        job_id=job_id,
        background_tasks=background_tasks,
        cache=cache,
        resume_store=resume_store,
        letter_store=letter_store,
        generation_store=generation_store,
        user_store=user_store,
        client=client,
    )


@router.get(
    "/users/{user_id}/letter-jobs/{generation_id}",
    response_model=LetterGenerationStatus,
)
def poll_letter_generation(
    user_id: str,
    generation_id: str,
    letter_store: LetterStore = Depends(get_letter_store),
    generation_store: LetterGenerationStore = Depends(get_letter_generation_store),
) -> LetterGenerationStatus:
    """Poll the status of an in-flight letter generation."""
    record = generation_store.get(user_id, generation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation '{generation_id}' not found for user '{user_id}'",
        )

    letter: Letter | None = None
    if record.status == "done" and record.saved_version is not None:
        stored = letter_store.get_version(
            user_id, record.job_id, record.saved_version
        )
        if stored is not None:
            letter = _to_response(stored)

    return LetterGenerationStatus(
        generation_id=record.generation_id,
        status=record.status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        letter=letter,
        error=record.error,
    )


@router.get(
    "/users/{user_id}/jobs/{job_id}/letters",
    response_model=LetterVersionList,
)
def list_letter_versions(
    user_id: str,
    job_id: str,
    letter_store: LetterStore = Depends(get_letter_store),
) -> LetterVersionList:
    """List all letter versions for one job (latest first)."""
    versions = letter_store.list_versions(user_id, job_id)
    versions.sort(key=lambda lt: lt.version, reverse=True)
    return LetterVersionList(
        versions=[_to_response(v) for v in versions],
        total=len(versions),
    )


@router.get(
    "/users/{user_id}/jobs/{job_id}/letters/{version}",
    response_model=Letter,
)
def get_letter_version(
    user_id: str,
    job_id: str,
    version: int,
    letter_store: LetterStore = Depends(get_letter_store),
) -> Letter:
    """Get one specific letter version."""
    stored = letter_store.get_version(user_id, job_id, version)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Letter version {version} not found for job '{job_id}', "
                f"user '{user_id}'"
            ),
        )
    return _to_response(stored)


@router.get(
    "/users/{user_id}/jobs/{job_id}/letters/{version}/download.md",
)
def download_letter_markdown(
    user_id: str,
    job_id: str,
    version: int,
    letter_store: LetterStore = Depends(get_letter_store),
) -> Response:
    """Download the letter text as raw Markdown."""
    stored = letter_store.get_version(user_id, job_id, version)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Letter version {version} not found",
        )
    filename = f"cover_letter_v{version}.md"
    return Response(
        content=stored.text,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ----- Helpers -----


def _start_generation(
    *,
    user_id: str,
    job_id: str,
    background_tasks: BackgroundTasks,
    cache: JobsCache,
    resume_store: ResumeStore,
    letter_store: LetterStore,
    generation_store: LetterGenerationStore,
    user_store: UserProfileStore,
    client: Anthropic,
) -> GenerateLetterResponse:
    generation_id = uuid.uuid4().hex[:12]
    generation_store.create(user_id, generation_id, job_id=job_id)
    background_tasks.add_task(
        _run_generation_in_background,
        user_id=user_id,
        job_id=job_id,
        generation_id=generation_id,
        cache=cache,
        resume_store=resume_store,
        letter_store=letter_store,
        generation_store=generation_store,
        user_store=user_store,
        client=client,
    )
    return GenerateLetterResponse(generation_id=generation_id, status="pending")


def _to_response(stored: StoredLetter) -> Letter:
    """Convert StoredLetter (domain) → Letter (API response shape)."""
    strategy = None
    if stored.strategy:
        try:
            strategy = Strategy(**stored.strategy)
        except Exception:  # noqa: BLE001
            # If a saved strategy doesn't match the current schema (older
            # versions might lack fields), surface as None rather than 500.
            strategy = None

    critique = None
    if stored.critique:
        try:
            scores = stored.critique.get("scores") or {}
            category_scores: dict[str, int] = {}
            failed: list[str] = []
            for cat, sc in scores.items():
                if isinstance(sc, dict):
                    if isinstance(sc.get("score"), int | float):
                        category_scores[cat] = int(sc["score"])
                    if sc.get("threshold_met") is False:
                        failed.append(cat)
            critique = CritiqueScore(
                total=int(stored.critique.get("total", 0)),
                verdict=stored.critique.get("verdict", "minor_revision"),
                category_scores=category_scores,
                failed_thresholds=failed,
                notes=stored.critique.get("notes", "") or "",
            )
        except Exception:  # noqa: BLE001
            critique = None

    return Letter(
        version=stored.version,
        text=stored.text,
        word_count=stored.word_count,
        strategy=strategy,
        critique=critique,
        feedback_used=stored.feedback_used,
        created_at=stored.created_at,
    )


def _run_generation_in_background(
    *,
    user_id: str,
    job_id: str,
    generation_id: str,
    cache: JobsCache,
    resume_store: ResumeStore,
    letter_store: LetterStore,
    generation_store: LetterGenerationStore,
    user_store: UserProfileStore,
    client: Anthropic,
) -> None:
    """The agent run, executed after the 202 response is sent."""
    try:
        generation_store.mark_running(user_id, generation_id)

        # 1. Find the JobPosting in the cached snapshot.
        job = _find_job(cache, user_id, job_id)
        if job is None:
            generation_store.mark_failed(
                user_id,
                generation_id,
                error=(
                    f"Job '{job_id}' not in current snapshot. "
                    "Refresh jobs first."
                ),
            )
            return

        # 2. Load + parse resume.
        resume_bytes = resume_store.get_file_bytes(user_id)
        if resume_bytes is None:
            generation_store.mark_failed(
                user_id,
                generation_id,
                error="No resume uploaded. Upload one before generating.",
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

        # 3. Load the user's profile (for the header block in the letter).
        try:
            user_profile = user_store.get_user(user_id)
        except FileNotFoundError as exc:
            generation_store.mark_failed(
                user_id,
                generation_id,
                error=f"User profile not found: {exc}",
            )
            return

        # 4. Run the Phase 4 agent. usage_tracker exposes strategy + critique.
        usage_tracker: dict = {}
        letter_text = generate_cover_letter_agent(
            user=user_profile,
            resume_text=resume_text,
            job=job,
            client=client,
            usage_tracker=usage_tracker,
        )

        # 5. Persist as a new version.
        saved = letter_store.save_letter(
            user_id,
            job_id,
            text=letter_text,
            strategy=usage_tracker.get("strategy"),
            critique=usage_tracker.get("last_critique"),
            feedback_used=None,
        )
        generation_store.mark_done(
            user_id, generation_id, saved_version=saved.version
        )

    except Exception as exc:  # noqa: BLE001
        generation_store.mark_failed(user_id, generation_id, error=str(exc))


def _find_job(
    cache: JobsCache, user_id: str, job_id: str
) -> JobPosting | None:
    snapshot = cache.get_snapshot(user_id)
    if snapshot is None:
        return None
    for stored in snapshot.jobs:
        if stored.job.id == job_id:
            return stored.job
    return None


__all__ = [
    "get_anthropic_client",
    "get_letter_generation_store",
    "get_letter_store",
    "router",
]
