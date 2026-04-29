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
    "CritiqueScore",
    "GenerateLetterRequest",
    "GenerateLetterResponse",
    "HealthResponse",
    "JobDetailResponse",
    "JobListResponse",
    "JobSummary",
    "Letter",
    "LetterGenerationStatus",
    "LetterVersionList",
    "ManualEditRequest",
    "QueryListResponse",
    "RefineLetterRequest",
    "RefreshJobResponse",
    "RefreshStatusResponse",
    "ResumeMetadata",
    "SavedQuery",
    "Strategy",
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
    total: int                          # count after all filters
    total_unfiltered: int = 0           # count before query-param filters
    hidden_by_filters: int = 0          # = total_unfiltered - total
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


# ----- Cover letters -----


class Strategy(BaseModel):
    """The agent's committed plan, surfaced in the UI."""

    fit_assessment: Literal["HIGH", "MEDIUM", "LOW"]
    fit_reasoning: str
    narrative_angle: str
    primary_project: str
    secondary_project: str | None = None


class CritiqueScore(BaseModel):
    """Subset of the rubric output the UI cares about."""

    total: int                          # 0-110
    verdict: Literal["approved", "minor_revision", "rewrite_required"]
    category_scores: dict[str, int]     # e.g. {"hallucination": 25, ...}
    failed_thresholds: list[str]
    notes: str = ""


class Letter(BaseModel):
    """One version of a saved cover letter (response shape)."""

    version: int
    text: str
    word_count: int
    strategy: Strategy | None = None
    critique: CritiqueScore | None = None
    feedback_used: str | None = None
    refinement_index: int = 0       # 0 for original, 1..10 for refines
    edited_by_user: bool = False    # true if user manually edited
    created_at: datetime


class LetterVersionList(BaseModel):
    """Body of GET /users/{user_id}/jobs/{job_id}/letters."""

    versions: list[Letter]              # latest first
    total: int


class GenerateLetterRequest(BaseModel):
    """Body of POST /users/{user_id}/jobs/{job_id}/letters.

    Reserved for future fields. Currently empty — the job_id in the URL
    plus the user's resume + queries is everything the agent needs.
    """

    pass


class GenerateLetterResponse(BaseModel):
    """Returned 202 immediately from generate / regenerate / refine."""

    generation_id: str
    status: Literal["pending"]
    estimated_seconds: int = 60


class LetterGenerationStatus(BaseModel):
    """Body of GET /users/{user_id}/letter-jobs/{generation_id}."""

    generation_id: str
    status: Literal["pending", "running", "done", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    letter: Letter | None = None        # populated when status="done"
    error: str | None = None


class RefineLetterRequest(BaseModel):
    """Body of POST /users/{user_id}/jobs/{job_id}/letters/{version}/refine."""

    feedback: str = Field(min_length=5, max_length=500)


class ManualEditRequest(BaseModel):
    """Body of POST /users/{user_id}/jobs/{job_id}/letters/{version}/edit.

    Validation here is gentler than the agent's hard limits — users get
    more freedom than the agent does. The deterministic checks
    (word count 200-500, paragraph length ≤ 200 words) live in the
    route, not the schema, since they require splitting the text.
    """

    text: str = Field(min_length=1, max_length=5000)
