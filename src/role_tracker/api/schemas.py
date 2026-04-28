"""Pydantic request/response models for the API.

These get filled in incrementally as routes land. See docs/api_spec.md
for the full set planned. Right now this only contains what the
existing routes use.
"""

from pydantic import BaseModel


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
