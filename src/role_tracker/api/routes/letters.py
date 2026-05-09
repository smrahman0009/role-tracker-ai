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

from role_tracker.api.routes.jobs import get_seen_jobs_store, get_usage_store
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.api.schemas import (
    CoverLetterAnalysisRequest,
    CoverLetterAnalysisResponse,
    CoverLetterSummaryRequest,
    CoverLetterSummaryResponse,
    CritiqueScore,
    GenerateLetterRequest,
    GenerateLetterResponse,
    Letter,
    LetterGenerationStatus,
    LetterVersionList,
    ManualEditRequest,
    PolishLetterRequest,
    PolishLetterResponse,
    PolishWhyInterestedRequest,
    RefineLetterRequest,
    Strategy,
    WhyInterestedResponse,
)
from role_tracker.config import Settings
from role_tracker.cover_letter.agent import generate_cover_letter_agent
from role_tracker.cover_letter.interactive import (
    SummaryError,
    resolve_model,
    summarize_job,
)
from role_tracker.cover_letter.polish import polish_cover_letter
from role_tracker.cover_letter.refine import refine_cover_letter
from role_tracker.jobs.models import JobPosting
from role_tracker.jobs.seen import SeenJobsStore
from role_tracker.letters.formats import letter_to_docx, letter_to_pdf
from role_tracker.letters.generation_state import (
    FileLetterGenerationStore,
    LetterGenerationStore,
)
from role_tracker.letters.header import with_current_header
from role_tracker.letters.models import StoredLetter
from role_tracker.letters.store import (
    MAX_REFINEMENTS_PER_LETTER,
    FileLetterStore,
    LetterStore,
)
from role_tracker.resume.parser import parse_resume
from role_tracker.resume.store import ResumeStore
from role_tracker.screening.why_interested import polish_why_interested
from role_tracker.usage import UsageRecorder, UsageStore
from role_tracker.usage.caps import enforce_daily_cap
from role_tracker.users.base import UserProfileStore
from role_tracker.users.models import UserProfile

router = APIRouter(tags=["letters"])


# ----- Dependencies -----


def get_letter_store() -> LetterStore:
    """Picks DynamoDB when STORAGE_BACKEND=aws, else file-backed."""
    settings = Settings()
    if settings.storage_backend == "aws":
        from role_tracker.aws.dynamodb_letter_store import DynamoDBLetterStore

        return DynamoDBLetterStore(
            table_name=settings.ddb_letters_table,
            region_name=settings.aws_region,
        )
    return FileLetterStore()


def get_letter_generation_store() -> LetterGenerationStore:
    return FileLetterGenerationStore()


def get_user_profile_store() -> UserProfileStore:
    """YAML in dev, DynamoDB in prod (STORAGE_BACKEND=aws). Tests
    override with a stub or a tmp-rooted YAML store."""
    from role_tracker.users.factory import make_user_profile_store

    return make_user_profile_store()


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
    body: GenerateLetterRequest,
    background_tasks: BackgroundTasks,
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    resume_store: ResumeStore = Depends(get_resume_store),
    letter_store: LetterStore = Depends(get_letter_store),
    generation_store: LetterGenerationStore = Depends(get_letter_generation_store),
    user_store: UserProfileStore = Depends(get_user_profile_store),
    client: Anthropic = Depends(get_anthropic_client),
    usage_store: UsageStore = Depends(get_usage_store),
) -> GenerateLetterResponse:
    """Kick off a cover-letter generation. Returns immediately."""
    return _start_generation(
        user_id=user_id,
        job_id=job_id,
        background_tasks=background_tasks,
        seen_store=seen_store,
        resume_store=resume_store,
        letter_store=letter_store,
        generation_store=generation_store,
        user_store=user_store,
        client=client,
        usage_store=usage_store,
        instruction=body.instruction,
        template=body.template,
        extended_thinking=body.extended_thinking,
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
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    resume_store: ResumeStore = Depends(get_resume_store),
    letter_store: LetterStore = Depends(get_letter_store),
    generation_store: LetterGenerationStore = Depends(get_letter_generation_store),
    user_store: UserProfileStore = Depends(get_user_profile_store),
    client: Anthropic = Depends(get_anthropic_client),
    usage_store: UsageStore = Depends(get_usage_store),
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
        seen_store=seen_store,
        resume_store=resume_store,
        letter_store=letter_store,
        generation_store=generation_store,
        user_store=user_store,
        client=client,
        usage_store=usage_store,
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
    user_store: UserProfileStore = Depends(get_user_profile_store),
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
            letter = _to_response(stored, _user_or_none(user_store, user_id))

    return LetterGenerationStatus(
        generation_id=record.generation_id,
        status=record.status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        letter=letter,
        error=record.error,
        phase=record.phase,
    )


@router.get(
    "/users/{user_id}/jobs/{job_id}/letters",
    response_model=LetterVersionList,
)
def list_letter_versions(
    user_id: str,
    job_id: str,
    letter_store: LetterStore = Depends(get_letter_store),
    user_store: UserProfileStore = Depends(get_user_profile_store),
) -> LetterVersionList:
    """List all letter versions for one job (latest first)."""
    versions = letter_store.list_versions(user_id, job_id)
    versions.sort(key=lambda lt: lt.version, reverse=True)
    user = _user_or_none(user_store, user_id)
    return LetterVersionList(
        versions=[_to_response(v, user) for v in versions],
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
    user_store: UserProfileStore = Depends(get_user_profile_store),
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
    return _to_response(stored, _user_or_none(user_store, user_id))


@router.post(
    "/users/{user_id}/jobs/{job_id}/letters/{version}/refine",
    response_model=GenerateLetterResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def refine_letter(
    user_id: str,
    job_id: str,
    version: int,
    body: RefineLetterRequest,
    background_tasks: BackgroundTasks,
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    resume_store: ResumeStore = Depends(get_resume_store),
    letter_store: LetterStore = Depends(get_letter_store),
    generation_store: LetterGenerationStore = Depends(get_letter_generation_store),
    user_store: UserProfileStore = Depends(get_user_profile_store),
    client: Anthropic = Depends(get_anthropic_client),
    usage_store: UsageStore = Depends(get_usage_store),
) -> GenerateLetterResponse:
    """Refine an existing letter version with free-text feedback.

    Returns a new generation_id; poll the same letter-jobs endpoint as
    initial generation. The refined letter becomes a new version in the
    same job's history (so you can compare drafts).

    Strategy is preserved — see cover_letter/refine.py for details.
    If the user wants to change strategy, they should call /regenerate
    instead.
    """
    # Verify the source version exists before kicking off the bg task.
    source = letter_store.get_version(user_id, job_id, version)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Letter version {version} not found for job '{job_id}', "
                f"user '{user_id}'"
            ),
        )

    # Per-letter refinement cap: don't allow refine #11+. Manual edits
    # don't count toward this; only refinement_index does.
    if letter_store.count_refinements(user_id, job_id) >= MAX_REFINEMENTS_PER_LETTER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{MAX_REFINEMENTS_PER_LETTER} refinements is the cap for this "
                "letter. Regenerate (POST /jobs/{job_id}/regenerate) for a "
                "fresh approach."
            ),
        )

    refine_feature = (
        "cover_letter_generate_extended"
        if body.extended_thinking
        else "cover_letter_refine"
    )
    enforce_daily_cap(usage_store, user_id, refine_feature)

    generation_id = uuid.uuid4().hex[:12]
    generation_store.create(user_id, generation_id, job_id=job_id)
    background_tasks.add_task(
        _run_refine_in_background,
        user_id=user_id,
        job_id=job_id,
        source_version=version,
        feedback=body.feedback,
        extended_thinking=body.extended_thinking,
        generation_id=generation_id,
        seen_store=seen_store,
        resume_store=resume_store,
        letter_store=letter_store,
        generation_store=generation_store,
        user_store=user_store,
        client=client,
        usage_store=usage_store,
    )
    return GenerateLetterResponse(generation_id=generation_id, status="pending")


@router.post(
    "/users/{user_id}/jobs/{job_id}/letters/{version}/edit",
    response_model=Letter,
    status_code=status.HTTP_201_CREATED,
)
def edit_letter(
    user_id: str,
    job_id: str,
    version: int,
    body: ManualEditRequest,
    letter_store: LetterStore = Depends(get_letter_store),
) -> Letter:
    """Save a user-edited version of a letter. Synchronous — no agent.

    The committed strategy carries forward unchanged. Critique is set to
    None because the agent's quality assessment doesn't apply to text
    the agent didn't write. Doesn't count toward the 10-refinement cap
    or the daily generation rate limit.
    """
    source = letter_store.get_version(user_id, job_id, version)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Letter version {version} not found for job '{job_id}', "
                f"user '{user_id}'"
            ),
        )

    # Gentle deterministic checks. Users get more freedom than the agent.
    word_count = len(body.text.split())
    if word_count < 200 or word_count > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Letter is {word_count} words; manual edits must be "
                "between 200 and 500."
            ),
        )
    paragraphs = [p.strip() for p in body.text.split("\n\n") if p.strip()]
    for i, p in enumerate(paragraphs, 1):
        if len(p.split()) > 200:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Paragraph {i} is {len(p.split())} words; manual edits "
                    "should keep paragraphs under 200 words."
                ),
            )

    saved = letter_store.save_letter(
        user_id,
        job_id,
        text=body.text,
        strategy=source.strategy,        # carries forward unchanged
        critique=None,                    # agent's grade no longer applies
        feedback_used="manual edit",
        refinement_index=source.refinement_index,  # not bumped
        edited_by_user=True,
    )
    return _to_response(saved)


@router.post(
    "/users/{user_id}/jobs/{job_id}/letters/{version}/polish",
    response_model=PolishLetterResponse,
)
def polish_letter(
    user_id: str,
    job_id: str,  # noqa: ARG001
    version: int,  # noqa: ARG001
    body: PolishLetterRequest,
    client: Anthropic = Depends(get_anthropic_client),
    usage_store: UsageStore = Depends(get_usage_store),
) -> PolishLetterResponse:
    """Fix grammar / clarity in user-edited cover letter text.

    Single Claude Haiku call (~$0.005, ~3s). Preserves meaning, length,
    paragraph breaks, bold markers, and link syntax. Does not save a new
    version — the frontend wires this into the existing Edit textarea so
    the user can polish, review, then click Save edit (which goes through
    the manual-edit endpoint as before).
    """
    enforce_daily_cap(usage_store, user_id, "cover_letter_polish")
    polished = polish_cover_letter(text=body.text, client=client)
    UsageRecorder(usage_store, user_id).feature("cover_letter_polish")
    return PolishLetterResponse(
        text=polished, word_count=len(polished.split())
    )


@router.post(
    "/users/{user_id}/jobs/{job_id}/cover-letter/analysis",
    response_model=CoverLetterAnalysisResponse,
)
def analyze_cover_letter_match(
    user_id: str,
    job_id: str,
    body: CoverLetterAnalysisRequest,
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    resume_store: ResumeStore = Depends(get_resume_store),
    client: Anthropic = Depends(get_anthropic_client),
    usage_store: UsageStore = Depends(get_usage_store),
) -> CoverLetterAnalysisResponse:
    """Resume↔JD match analysis: four lists (Strong / Gaps / Partial /
    excitement hooks) inspectable on the job-detail page.

    The user reads the lists and can mention specific gaps or
    excitement hooks in the Generate dialog's instruction field
    ("address the distributed-systems gap", "lead with the fraud-
    detection angle"). The agent never reads the analysis directly.

    Sonnet by default — better judgment than Haiku at picking what's
    distinctive about the overlap. Haiku is selectable per call for
    a cheaper run.
    """
    from role_tracker.cover_letter.interactive import (
        _ANALYSIS_MODEL_DEFAULT,
        AnalysisError,
        analyze,
    )

    job = _find_job(seen_store, user_id, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    resume_bytes = resume_store.get_file_bytes(user_id)
    if resume_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No resume uploaded. Upload one before running analysis.",
        )

    enforce_daily_cap(usage_store, user_id, "cover_letter_analysis")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(resume_bytes)
        tmp_path = Path(tmp.name)
    try:
        resume_text = parse_resume(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    model_id = resolve_model(body.model, default=_ANALYSIS_MODEL_DEFAULT)

    try:
        analysis = analyze(
            resume_text=resume_text,
            jd_text=job.description,
            client=client,
            model=model_id,
        )
    except AnalysisError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Match analysis failed to produce valid JSON. "
                f"Try again. ({exc})"
            ),
        ) from exc

    UsageRecorder(usage_store, user_id).feature("cover_letter_analysis")
    return CoverLetterAnalysisResponse(
        strong=analysis.strong,
        gaps=analysis.gaps,
        partial=analysis.partial,
        excitement_hooks=analysis.excitement_hooks,
        model=model_id,
    )


@router.post(
    "/users/{user_id}/jobs/{job_id}/cover-letter/summary",
    response_model=CoverLetterSummaryResponse,
)
def summarize_cover_letter_job(
    user_id: str,
    job_id: str,
    body: CoverLetterSummaryRequest,
    seen_store: SeenJobsStore = Depends(get_seen_jobs_store),
    client: Anthropic = Depends(get_anthropic_client),
    usage_store: UsageStore = Depends(get_usage_store),
) -> CoverLetterSummaryResponse:
    """Plain-English 5-6 sentence summary of the JD.

    Independent of the user's resume; this is purely a JD digest. Sonnet
    by default because the output is creative prose. Haiku is selectable
    via the `model` field for cost-vs-quality comparison.
    """
    from role_tracker.cover_letter.interactive import _SUMMARY_MODEL_DEFAULT

    job = _find_job(seen_store, user_id, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    enforce_daily_cap(usage_store, user_id, "cover_letter_summary")

    model_id = resolve_model(body.model, default=_SUMMARY_MODEL_DEFAULT)
    try:
        summary = summarize_job(
            jd_text=job.description,
            client=client,
            model=model_id,
        )
    except SummaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Job summary failed to produce valid JSON. "
                f"Try again. ({exc})"
            ),
        ) from exc

    UsageRecorder(usage_store, user_id).feature("cover_letter_summary")
    return CoverLetterSummaryResponse(
        role=summary.role,
        requirements=summary.requirements,
        context=summary.context,
        model=model_id,
    )


@router.get(
    "/users/{user_id}/jobs/{job_id}/letters/{version}/download.pdf",
)
def download_letter_pdf(
    user_id: str,
    job_id: str,
    version: int,
    letter_store: LetterStore = Depends(get_letter_store),
    user_store: UserProfileStore = Depends(get_user_profile_store),
) -> Response:
    """Download the letter as a US-Letter PDF (default — accepted everywhere).

    Renders with the current profile's contact header (live header), then
    measures page count. If the letter spills past one page, the response
    includes an `X-Letter-Pages` header so the frontend can surface a
    warning toast — we do NOT silently shrink the font, since that would
    be inconsistent across letters and not what the user wants for an
    important document.
    """
    stored = _require_letter(letter_store, user_id, job_id, version)
    rendered_text = with_current_header(
        text=stored.text,
        user=_user_or_none(user_store, user_id) or _placeholder_user(user_id),
        edited_by_user=stored.edited_by_user,
    )
    pdf_bytes, page_count = letter_to_pdf(rendered_text, with_page_count=True)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="cover_letter_v{version}.pdf"'
            ),
            "X-Letter-Pages": str(page_count),
            "Access-Control-Expose-Headers": "X-Letter-Pages",
        },
    )


@router.get(
    "/users/{user_id}/jobs/{job_id}/letters/{version}/download.docx",
)
def download_letter_docx(
    user_id: str,
    job_id: str,
    version: int,
    letter_store: LetterStore = Depends(get_letter_store),
    user_store: UserProfileStore = Depends(get_user_profile_store),
) -> Response:
    """Download the letter as Word .docx (best for ATS text extraction).

    DOCX pagination depends on the user's Word/LibreOffice version, so we
    don't try to enforce one-page in code — content discipline (the
    300-400 word agent cap, the 200-words-per-paragraph manual-edit rule)
    keeps it close. We still apply the live header so toggling fields in
    Settings propagates to the file.
    """
    stored = _require_letter(letter_store, user_id, job_id, version)
    rendered_text = with_current_header(
        text=stored.text,
        user=_user_or_none(user_store, user_id) or _placeholder_user(user_id),
        edited_by_user=stored.edited_by_user,
    )
    return Response(
        content=letter_to_docx(rendered_text),
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="cover_letter_v{version}.docx"'
            ),
        },
    )


def _placeholder_user(user_id: str) -> UserProfile:
    """Used when no profile exists yet — returns a profile whose name
    won't match the agent-generated header pattern, so with_current_header
    will leave the stored text alone rather than prepending an empty
    header. Belt-and-braces: with_current_header also short-circuits when
    contact_header() is empty."""
    return UserProfile(
        id=user_id,
        name="",
        resume_path=Path(""),
        queries=[],
    )


def _user_or_none(
    user_store: UserProfileStore, user_id: str
) -> UserProfile | None:
    """Look up the user profile, or None if it doesn't exist yet.
    Used to drive the live header substitution; missing profile means
    we render the stored letter text as-is."""
    try:
        return user_store.get_user(user_id)
    except FileNotFoundError:
        return None


def _require_letter(
    letter_store: LetterStore, user_id: str, job_id: str, version: int
) -> StoredLetter:
    stored = letter_store.get_version(user_id, job_id, version)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Letter version {version} not found",
        )
    return stored


# ----- "Why interested?" — polish only -----
#
# The motivation generator was removed in May 2026 — see
# docs/HANDBOOK.md and src/role_tracker/screening/why_interested.py.
# All that remains is a grammar-fix pass over text the user typed
# themselves.


@router.post(
    "/users/{user_id}/jobs/{job_id}/why-interested/polish",
    response_model=WhyInterestedResponse,
)
def polish_why_interested_answer(
    user_id: str,
    job_id: str,  # noqa: ARG001
    body: PolishWhyInterestedRequest,
    client: Anthropic = Depends(get_anthropic_client),
    usage_store: UsageStore = Depends(get_usage_store),
) -> WhyInterestedResponse:
    """Fix grammar / clarity in user-edited why-interested text.

    Single Claude Haiku call, ~3s, ~$0.005. Preserves meaning and
    length; doesn't introduce new ideas.
    """
    enforce_daily_cap(usage_store, user_id, "why_interested_polish")
    polished = polish_why_interested(text=body.text, client=client)
    UsageRecorder(usage_store, user_id).feature("why_interested_polish")
    return WhyInterestedResponse(
        text=polished, word_count=len(polished.split())
    )


# ----- Helpers -----


def _start_generation(
    *,
    user_id: str,
    job_id: str,
    background_tasks: BackgroundTasks,
    seen_store: SeenJobsStore,
    resume_store: ResumeStore,
    letter_store: LetterStore,
    generation_store: LetterGenerationStore,
    user_store: UserProfileStore,
    client: Anthropic,
    usage_store: UsageStore,
    instruction: str | None = None,
    template: str | None = None,
    extended_thinking: bool = False,
) -> GenerateLetterResponse:
    feature = (
        "cover_letter_generate_extended"
        if extended_thinking
        else "cover_letter_generate"
    )
    enforce_daily_cap(usage_store, user_id, feature)
    generation_id = uuid.uuid4().hex[:12]
    generation_store.create(user_id, generation_id, job_id=job_id)
    background_tasks.add_task(
        _run_generation_in_background,
        user_id=user_id,
        job_id=job_id,
        generation_id=generation_id,
        seen_store=seen_store,
        resume_store=resume_store,
        letter_store=letter_store,
        generation_store=generation_store,
        user_store=user_store,
        client=client,
        usage_store=usage_store,
        instruction=instruction,
        template=template,
        extended_thinking=extended_thinking,
    )
    return GenerateLetterResponse(generation_id=generation_id, status="pending")


def _to_response(
    stored: StoredLetter, user: UserProfile | None = None
) -> Letter:
    """Convert StoredLetter (domain) → Letter (API response shape).

    If `user` is provided, the contact header is substituted with the
    user's *current* profile (skipped for letters with edited_by_user=True
    — see letters/header.py for the contract).
    """
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

    rendered_text = stored.text
    if user is not None:
        rendered_text = with_current_header(
            text=stored.text,
            user=user,
            edited_by_user=stored.edited_by_user,
        )

    return Letter(
        version=stored.version,
        text=rendered_text,
        word_count=stored.word_count,
        strategy=strategy,
        critique=critique,
        feedback_used=stored.feedback_used,
        refinement_index=stored.refinement_index,
        edited_by_user=stored.edited_by_user,
        created_at=stored.created_at,
    )


def _run_generation_in_background(
    *,
    user_id: str,
    job_id: str,
    generation_id: str,
    seen_store: SeenJobsStore,
    resume_store: ResumeStore,
    letter_store: LetterStore,
    generation_store: LetterGenerationStore,
    user_store: UserProfileStore,
    client: Anthropic,
    usage_store: UsageStore,
    instruction: str | None = None,
    template: str | None = None,
    extended_thinking: bool = False,
) -> None:
    """The agent run, executed after the 202 response is sent."""
    try:
        generation_store.mark_running(user_id, generation_id)

        # 1. Find the JobPosting in the cached snapshot.
        job = _find_job(seen_store, user_id, job_id)
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

        # 4. Run the agent. usage_tracker exposes strategy + critique.
        usage_tracker: dict = {}

        def _report_phase(label: str) -> None:
            generation_store.mark_phase(user_id, generation_id, label)

        letter_text = generate_cover_letter_agent(
            user=user_profile,
            resume_text=resume_text,
            job=job,
            client=client,
            usage_tracker=usage_tracker,
            instruction=instruction,
            template=template,
            extended_thinking=extended_thinking,
            on_phase=_report_phase,
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
        feature = (
            "cover_letter_generate_extended"
            if extended_thinking
            else "cover_letter_generate"
        )
        UsageRecorder(usage_store, user_id).feature(feature)

    except Exception as exc:  # noqa: BLE001
        generation_store.mark_failed(user_id, generation_id, error=str(exc))


def _find_job(
    seen_store: SeenJobsStore, user_id: str, job_id: str
) -> JobPosting | None:
    """Look up a job in the long-lived per-user index."""
    stored = seen_store.get(user_id, job_id)
    return stored.job if stored else None


def _run_refine_in_background(
    *,
    user_id: str,
    job_id: str,
    source_version: int,
    feedback: str,
    generation_id: str,
    seen_store: SeenJobsStore,
    resume_store: ResumeStore,
    letter_store: LetterStore,
    generation_store: LetterGenerationStore,
    user_store: UserProfileStore,
    client: Anthropic,
    usage_store: UsageStore,
    extended_thinking: bool = False,
) -> None:
    """Run a single Sonnet call to refine the existing letter."""
    try:
        generation_store.mark_running(user_id, generation_id)

        source = letter_store.get_version(user_id, job_id, source_version)
        if source is None:
            generation_store.mark_failed(
                user_id,
                generation_id,
                error=f"Source version {source_version} no longer exists",
            )
            return
        if not source.strategy:
            generation_store.mark_failed(
                user_id,
                generation_id,
                error=(
                    "Source letter has no committed strategy. "
                    "Refinement requires a strategy to preserve. "
                    "Use /regenerate instead."
                ),
            )
            return

        job = _find_job(seen_store, user_id, job_id)
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

        resume_bytes = resume_store.get_file_bytes(user_id)
        if resume_bytes is None:
            generation_store.mark_failed(
                user_id,
                generation_id,
                error="No resume uploaded.",
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

        try:
            user_profile = user_store.get_user(user_id)
        except FileNotFoundError as exc:
            generation_store.mark_failed(
                user_id,
                generation_id,
                error=f"User profile not found: {exc}",
            )
            return

        revised_text = refine_cover_letter(
            user=user_profile,
            resume_text=resume_text,
            job=job,
            previous_letter=source.text,
            previous_strategy=source.strategy,
            feedback=feedback,
            client=client,
            extended_thinking=extended_thinking,
        )

        # Persist as a new version. Strategy carries forward unchanged
        # (preserved by the refine flow); critique is None because we
        # didn't run the rubric on this revision. refinement_index bumps
        # by 1 from the source version's index — manual edits in between
        # don't affect this count.
        saved = letter_store.save_letter(
            user_id,
            job_id,
            text=revised_text,
            strategy=source.strategy,
            critique=None,
            feedback_used=feedback,
            refinement_index=source.refinement_index + 1,
        )
        generation_store.mark_done(
            user_id, generation_id, saved_version=saved.version
        )
        refine_recorded_feature = (
            "cover_letter_generate_extended"
            if extended_thinking
            else "cover_letter_refine"
        )
        UsageRecorder(usage_store, user_id).feature(refine_recorded_feature)
    except Exception as exc:  # noqa: BLE001
        generation_store.mark_failed(user_id, generation_id, error=str(exc))


__all__ = [
    "get_anthropic_client",
    "get_letter_generation_store",
    "get_letter_store",
    "router",
]
