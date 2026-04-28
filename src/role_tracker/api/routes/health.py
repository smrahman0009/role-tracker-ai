"""Liveness check — used by Azure App Service health probe and dev sanity."""

from fastapi import APIRouter

from role_tracker.api.schemas import HealthResponse

router = APIRouter(tags=["meta"])

# Pulled from pyproject.toml at runtime to keep one source of truth.
_VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return 200 if the service is up. No auth required."""
    return HealthResponse(status="ok", version=_VERSION)
