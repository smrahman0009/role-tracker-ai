"""Domain model for resume metadata."""

from datetime import datetime

from pydantic import BaseModel


class ResumeMetadata(BaseModel):
    """Information about a user's stored resume — does not include the PDF bytes."""

    filename: str           # original filename from upload
    size_bytes: int         # current file size on disk
    uploaded_at: datetime   # when last replaced
    sha256: str             # content hash; used to detect re-embedding need
