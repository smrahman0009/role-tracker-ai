"""HTTP middleware for the API — bearer-token auth.

Reads the expected token from settings (`APP_TOKEN` env var). Every
request must include `Authorization: Bearer <token>` matching it,
EXCEPT requests to paths in the exempt set (health checks, OpenAPI docs).

If the configured token is empty, the middleware skips the check
entirely. This is the local-dev mode — set `APP_TOKEN` to enable
production-grade gating.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Paths that are reachable without a bearer token.
# - /health: Azure liveness probes can't send headers
# - /docs, /openapi.json, /redoc: API docs UI is harmless to expose
DEFAULT_EXEMPT_PATHS: frozenset[str] = frozenset(
    {"/health", "/docs", "/openapi.json", "/redoc"}
)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Reject requests without a matching `Authorization: Bearer <token>`."""

    def __init__(
        self,
        app,  # type: ignore[no-untyped-def]
        token: str = "",
        exempt_paths: frozenset[str] = DEFAULT_EXEMPT_PATHS,
    ) -> None:
        super().__init__(app)
        self.token = token
        self.exempt_paths = exempt_paths

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Dev mode: token unset → bypass auth entirely.
        if not self.token:
            return await call_next(request)

        if request.url.path in self.exempt_paths:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"detail": "Missing or malformed Authorization header"},
                status_code=401,
            )
        provided = auth_header.removeprefix("Bearer ").strip()
        if provided != self.token:
            return JSONResponse({"detail": "Invalid token"}, status_code=401)

        return await call_next(request)
