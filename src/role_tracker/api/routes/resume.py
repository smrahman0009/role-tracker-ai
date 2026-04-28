"""Resume endpoints — see docs/api_spec.md §2.

Three operations on a single resume per user:
- POST /users/{user_id}/resume       upload (replaces any existing)
- GET  /users/{user_id}/resume       metadata
- GET  /users/{user_id}/resume/file  download the PDF bytes
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from role_tracker.api.schemas import ResumeMetadata
from role_tracker.resume.store import FileResumeStore, ResumeStore

router = APIRouter(
    prefix="/users/{user_id}/resume",
    tags=["resume"],
)

MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5 MB


def get_resume_store() -> ResumeStore:
    """FastAPI dependency factory. Tests override this with a tmp-rooted store."""
    return FileResumeStore()


@router.post(
    "",
    response_model=ResumeMetadata,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    user_id: str,
    file: UploadFile = File(...),
    store: ResumeStore = Depends(get_resume_store),
) -> ResumeMetadata:
    """Upload (or replace) the resume PDF for a user. Max 5 MB.

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
    return store.save_resume(user_id, content=content, filename=filename)


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
