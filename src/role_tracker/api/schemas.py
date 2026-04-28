"""Pydantic request/response models for the API.

These get filled in incrementally as routes land. See docs/api_spec.md
for the full set planned. Domain models like SavedQuery are imported
from their domain modules — we don't duplicate them here.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from role_tracker.queries.models import SavedQuery
from role_tracker.resume.models import ResumeMetadata

__all__ = [
    "ApiError",
    "CreateQueryRequest",
    "HealthResponse",
    "QueryListResponse",
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
