"""Pydantic request/response models for the API.

These get filled in incrementally as routes land. See docs/api_spec.md
for the full set planned. Domain models like SavedQuery are imported
from their domain modules — we don't duplicate them here.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from role_tracker.queries.models import SavedQuery
from role_tracker.resume.models import ResumeMetadata

__all__ = [
    "ApiError",
    "CreateQueryRequest",
    "HealthResponse",
    "JobDetailResponse",
    "JobListResponse",
    "JobSummary",
    "QueryListResponse",
    "RefreshJobResponse",
    "RefreshStatusResponse",
    "ResumeMetadata",
    "SavedQuery",
    "UpdateQueryRequest",
]


class HealthResponse(BaseModel):
    """Liveness probe response. Used by Azure App Service health checks."""

    status: str
    version: str


class ApiError(BaseModel):
    """Custom error envelope for non-validation errors.

    FastAPI's automatic Pydantic validation errors use a different
    `{"detail": [...]}` shape; this `{"detail": "..."}` shape is for
    business-logic errors we raise ourselves.
    """

    detail: str


# ----- Saved queries -----


class QueryListResponse(BaseModel):
    """Body of GET /users/{user_id}/queries."""

    queries: list[SavedQuery]
    next_refresh_allowed_at: datetime | None = None


class CreateQueryRequest(BaseModel):
    """Body of POST /users/{user_id}/queries."""

    what: str = Field(min_length=1, max_length=200)
    where: str = Field(min_length=1, max_length=200)


class UpdateQueryRequest(BaseModel):
    """Body of PUT /users/{user_id}/queries/{query_id}.

    Every field is optional — only provided fields get patched.
    """

    what: str | None = Field(default=None, min_length=1, max_length=200)
    where: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None


# ----- Jobs -----

JobFilter = Literal["all", "unapplied", "applied"]


class JobSummary(BaseModel):
    """Slim job shape for list views — no full description."""

    job_id: str
    title: str
    company: str
    location: str
    posted_at: str
    salary_min: float | None = None
    salary_max: float | None = None
    publisher: str
    url: str
    match_score: float
    fit_assessment: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    applied: bool = False
    description_preview: str


class JobListResponse(BaseModel):
    """Body of GET /users/{user_id}/jobs."""

    jobs: list[JobSummary]
    total: int
    last_refreshed_at: datetime | None
    next_refresh_allowed_at: datetime | None = None


class JobDetailResponse(BaseModel):
    """Body of GET /users/{user_id}/jobs/{job_id} — full JD included."""

    job_id: str
    title: str
    company: str
    location: str
    posted_at: str
    salary_min: float | None = None
    salary_max: float | None = None
    publisher: str
    url: str
    description: str
    match_score: float
    fit_assessment: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    applied: bool = False


class RefreshJobResponse(BaseModel):
    """Body of POST /users/{user_id}/jobs/refresh — returned 202 immediately."""

    refresh_id: str
    status: Literal["pending"]


class RefreshStatusResponse(BaseModel):
    """Body of GET /users/{user_id}/jobs/refresh/{refresh_id}."""

    refresh_id: str
    status: Literal["pending", "running", "done", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    jobs_added: int | None = None
    error: str | None = None
