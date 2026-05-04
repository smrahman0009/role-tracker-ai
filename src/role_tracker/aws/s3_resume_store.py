"""S3-backed ResumeStore.

Implements the same Protocol as FileResumeStore. Each user's resume
PDF is stored at:

    s3://{bucket}/resumes/{user_id}.pdf

with object metadata carrying the original filename and the
uploaded_at timestamp:

    Metadata={"original-filename": "...", "uploaded-at": "ISO-8601"}

S3 itself reports the object size and computes a strong ETag we can
use as the SHA-256 fingerprint... almost — the ETag is MD5 for small
single-part uploads and a different format for multipart, so we
compute the SHA-256 ourselves on write and stash it in user-metadata.

Reads pull only object headers when possible to keep traffic small;
the full file is fetched only when a caller explicitly asks for the
bytes (e.g. for resume parsing on the matching pipeline).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from role_tracker.resume.models import ResumeMetadata


def _key(user_id: str) -> str:
    return f"resumes/{user_id}.pdf"


class S3ResumeStore:
    """ResumeStore backed by an S3 bucket."""

    def __init__(
        self,
        bucket: str,
        *,
        region_name: str | None = None,
        s3_client: object | None = None,
    ) -> None:
        if s3_client is None:
            s3_client = boto3.client("s3", region_name=region_name)
        self._client = s3_client
        self._bucket = bucket

    # ----- Protocol methods -----

    def get_metadata(self, user_id: str) -> ResumeMetadata | None:
        try:
            response = self._client.head_object(
                Bucket=self._bucket, Key=_key(user_id)
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"404", "NoSuchKey"}:
                return None
            raise

        user_meta = response.get("Metadata", {}) or {}
        original_filename = user_meta.get(
            "original-filename", f"{user_id}.pdf"
        )
        uploaded_at_raw = user_meta.get("uploaded-at")
        uploaded_at = (
            datetime.fromisoformat(uploaded_at_raw)
            if uploaded_at_raw
            else response.get("LastModified", datetime.now(UTC))
        )
        sha256 = user_meta.get("sha256", "")
        size_bytes = int(response.get("ContentLength", 0))

        return ResumeMetadata(
            filename=original_filename,
            size_bytes=size_bytes,
            uploaded_at=uploaded_at,
            sha256=sha256,
        )

    def get_file_bytes(self, user_id: str) -> bytes | None:
        try:
            response = self._client.get_object(
                Bucket=self._bucket, Key=_key(user_id)
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"404", "NoSuchKey"}:
                return None
            raise
        return response["Body"].read()

    def save_resume(
        self, user_id: str, *, content: bytes, filename: str
    ) -> ResumeMetadata:
        now = datetime.now(UTC)
        sha256 = hashlib.sha256(content).hexdigest()

        self._client.put_object(
            Bucket=self._bucket,
            Key=_key(user_id),
            Body=content,
            ContentType="application/pdf",
            Metadata={
                "original-filename": filename,
                "uploaded-at": now.isoformat(),
                "sha256": sha256,
            },
        )

        return ResumeMetadata(
            filename=filename,
            size_bytes=len(content),
            uploaded_at=now,
            sha256=sha256,
        )
