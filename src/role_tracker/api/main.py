"""FastAPI app factory for Role Tracker.

Entry points:
- `app` — the module-level instance, used by uvicorn.
- `create_app()` — factory used by tests so each test can build a fresh
  app instance with its own settings (env-var-driven).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from role_tracker.api.middleware import BearerTokenMiddleware, parse_tokens
from role_tracker.api.routes import (
    admin,
    health,
    jobs,
    letters,
    profile,
    queries,
    resume,
    usage,
)
from role_tracker.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hook. Wired-up DB clients land here in later commits."""
    yield


def create_app() -> FastAPI:
    """Build a FastAPI app from current environment settings."""
    settings = Settings()

    app = FastAPI(
        title="Role Tracker API",
        version="0.1.0",
        description=(
            "HTTP API for the Role Tracker agent. "
            "See docs/api_spec.md for the contract."
        ),
        lifespan=lifespan,
    )

    # CORS — allow only the frontend origin in production; allow localhost
    # by default so React's `npm run dev` works out of the box.
    cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Bearer-token auth. Multi-user mode (APP_TOKENS JSON) takes
    # precedence over the legacy single-token APP_TOKEN; both unset =
    # dev mode bypass.
    tokens = parse_tokens(settings.app_tokens)
    app.add_middleware(
        BearerTokenMiddleware,
        token=settings.app_token,
        tokens=tokens,
    )

    # Routes.
    app.include_router(health.router)
    app.include_router(queries.router)
    app.include_router(resume.router)
    app.include_router(jobs.router)
    app.include_router(letters.router)
    app.include_router(profile.router)
    app.include_router(usage.router)
    app.include_router(admin.router)

    return app


app = create_app()
