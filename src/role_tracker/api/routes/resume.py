"""Resume endpoints — see docs/api_spec.md §2.

Three operations on a single resume per user:
- POST /users/{user_id}/resume       upload (replaces any existing)
- GET  /users/{user_id}/resume       metadata
- GET  /users/{user_id}/resume/file  download the PDF bytes
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from role_tracker.api.routes.profile import get_profile_store
from role_tracker.api.schemas import ResumeMetadata
from role_tracker.resume.extract import extract_contact_info
from role_tracker.resume.parser import parse_resume
from role_tracker.resume.store import FileResumeStore, ResumeStore
from role_tracker.users.base import UserProfileStore
from role_tracker.users.models import UserProfile


class ResumeUploadResponse(ResumeMetadata):
    """POST /resume returns metadata plus the list of profile fields
    we auto-filled from the resume text. The frontend uses
    `prefilled_fields` to surface a one-time toast like
    'Pre-filled name, email, phone from your resume — review in Settings'.
    """

    prefilled_fields: list[str] = []

router = APIRouter(
    prefix="/users/{user_id}/resume",
    tags=["resume"],
)

MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5 MB


def get_resume_store() -> ResumeStore:
    """FastAPI dependency factory.

    Picks the S3-backed store when STORAGE_BACKEND=aws, else the
    local-disk file store. Tests override this with a tmp-rooted
    store at the FastAPI level.
    """
    from role_tracker.config import Settings

    settings = Settings()
    if settings.storage_backend == "aws":
        from role_tracker.aws.s3_resume_store import S3ResumeStore

        return S3ResumeStore(
            bucket=settings.s3_bucket,
            region_name=settings.aws_region,
        )
    return FileResumeStore()


@router.post(
    "",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    user_id: str,
    file: UploadFile = File(...),
    store: ResumeStore = Depends(get_resume_store),
    profile_store: UserProfileStore = Depends(get_profile_store),
) -> ResumeUploadResponse:
    """Upload (or replace) the resume PDF for a user. Max 5 MB.

    Beyond storing the binary, we parse the text and pull out
    name / email / phone / linkedin / github so the user doesn't have
    to retype them in Settings. Existing non-empty fields on the
    profile are preserved — extracted values only fill gaps.

    The MIME type check is intentionally permissive — some browsers send
    `application/octet-stream` for PDFs from disk. We do a content sniff
    on the first bytes to confirm it's a real PDF.
    """
    content = await file.read()
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum is {MAX_RESUME_BYTES // 1024 // 1024} MB",
        )
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a valid PDF (missing %PDF- header)",
        )
    filename = file.filename or f"{user_id}.pdf"
    metadata = store.save_resume(user_id, content=content, filename=filename)

    prefilled = _autofill_profile_from_resume(
        user_id, content, profile_store
    )
    return ResumeUploadResponse(
        **metadata.model_dump(),
        prefilled_fields=prefilled,
    )


def _autofill_profile_from_resume(
    user_id: str,
    pdf_bytes: bytes,
    profile_store: UserProfileStore,
) -> list[str]:
    """Parse the PDF, extract contact info, fill any blank profile fields.

    Returns the names of fields that were actually written. Existing
    non-empty values on the profile are preserved — we never overwrite
    something the user has already typed.
    """
    # Parse to text via a temp file (pypdf wants a path).
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)
    try:
        text = parse_resume(tmp_path)
    except Exception:  # noqa: BLE001 — never fail the upload over extraction
        return []
    finally:
        tmp_path.unlink(missing_ok=True)

    extracted = extract_contact_info(text)
    extracted_dict = extracted.model_dump()
    candidates = {k: v for k, v in extracted_dict.items() if v}
    if not candidates:
        return []

    try:
        profile = profile_store.get_user(user_id)
    except FileNotFoundError:
        # Fresh user — build a minimal profile we can fill in.
        # Leave name blank so the update loop below picks it up as
        # "prefilled from resume" rather than skipping it as already-set.
        profile = UserProfile(
            id=user_id,
            name="",
            resume_path=Path(""),
            queries=[],
        )

    # Only overwrite fields the user has left blank.
    updates: dict[str, str] = {}
    for field, value in candidates.items():
        current = getattr(profile, field, "")
        if isinstance(current, str) and not current.strip():
            updates[field] = value

    if not updates:
        return []

    profile_store.save_user(profile.model_copy(update=updates))
    return list(updates.keys())


@router.get("", response_model=ResumeMetadata)
def get_resume_metadata(
    user_id: str,
    store: ResumeStore = Depends(get_resume_store),
) -> ResumeMetadata:
    """Return metadata only — does NOT return the PDF bytes themselves."""
    metadata = store.get_metadata(user_id)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No resume uploaded for user '{user_id}'",
        )
    return metadata


@router.get("/file")
def download_resume(
    user_id: str,
    store: ResumeStore = Depends(get_resume_store),
) -> Response:
    """Return the original PDF bytes."""
    content = store.get_file_bytes(user_id)
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No resume uploaded for user '{user_id}'",
        )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{user_id}.pdf"',
        },
    )
