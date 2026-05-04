"""Production ASGI app — single container serving both the API and the SPA.

Layout:
    /api/*    → the FastAPI app from role_tracker.api.main
    /         → the built React SPA (frontend/dist)
    /<route>  → falls back to index.html so client-side routing works

The dev workflow is unchanged: developers run uvicorn against
`role_tracker.api.main:app` and Vite proxies /api/* to it. This
module is only imported in the Docker image entrypoint.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def _load_secrets_if_aws() -> None:
    """When running with STORAGE_BACKEND=aws, fetch API keys from SSM
    Parameter Store and inject them into the process env BEFORE the
    inner API app reads `Settings()`. Local dev (file backend) skips
    this step entirely so it never needs AWS credentials."""
    if os.environ.get("STORAGE_BACKEND", "file") != "aws":
        return
    prefix = os.environ.get("SSM_PREFIX", "/role-tracker")
    region = os.environ.get("AWS_REGION")
    try:
        # Imported lazily so the file-backed dev path doesn't require boto3
        # at module load time.
        from role_tracker.aws.ssm_secrets import load_secrets_into_env

        load_secrets_into_env(prefix=prefix, region_name=region)
    except Exception as exc:  # noqa: BLE001
        # Don't crash the whole app if SSM is unavailable — the
        # operator can still SSH in and see what went wrong via logs.
        # The API itself will return 5xx on routes that need a key,
        # which is the correct behaviour anyway.
        logger.error("SSM secret load failed: %s", exc)


# Run BEFORE we import api.main, so when its module-level
# `app = create_app()` line evaluates, env vars are already populated
# and `Settings()` reads the right values.
_load_secrets_if_aws()

from role_tracker.api.main import create_app as create_api_app  # noqa: E402


def _frontend_dist() -> Path:
    """Resolve the path to frontend/dist.

    Override with FRONTEND_DIST env var when the bundle lives somewhere
    unusual (Docker mounts it under /app/frontend/dist by default).
    """
    explicit = os.environ.get("FRONTEND_DIST")
    if explicit:
        return Path(explicit)
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_full_app() -> FastAPI:
    api_app = create_api_app()
    app = FastAPI(
        title="Role Tracker",
        version="0.1.0",
        description="Single-container app: SPA at /, API at /api.",
    )
    app.mount("/api", api_app)

    dist = _frontend_dist()
    if not dist.exists():
        # In non-frontend test contexts (or before the first build) we
        # still want the API to come up — the SPA mount is optional.
        return app

    # /assets/* is the hashed Vite bundle; mount it directly so it
    # 404s cleanly for missing files instead of falling through to
    # the SPA fallback.
    assets_dir = dist / "assets"
    if assets_dir.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="assets",
        )

    index_file = dist / "index.html"

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        """Serve a static file from dist/ if it exists, else index.html.

        This makes client-side routes like /jobs/abc work after a hard
        reload — the browser asks for /jobs/abc, we hand back index.html,
        React Router takes over.
        """
        # Prevent path traversal — Path("../etc/passwd") resolves
        # outside dist/ and is rejected.
        candidate = (dist / full_path).resolve()
        try:
            candidate.relative_to(dist.resolve())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not found",
            ) from exc

        if candidate.is_file():
            return FileResponse(candidate)
        if not index_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Frontend bundle missing",
            )
        return FileResponse(index_file)

    return app


app = create_full_app()
