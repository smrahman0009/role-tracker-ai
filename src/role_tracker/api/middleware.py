"""HTTP middleware for the API — bearer-token auth + path enforcement.

Three modes, picked from settings at startup:

1. **Multi-user** (`app_tokens` set): JSON map of `{token: user_id}`.
   Each token is bound to one user_id. If the request URL targets
   `/users/{x}/...` (or `/api/users/{x}/...`), `x` must match the
   token's bound user_id, else 403. Tokens not in the map → 401.

2. **Legacy single-token** (`app_token` set, `app_tokens` empty): one
   secret with no per-user binding. Any user_id in the URL is allowed.
   Kept so the existing single-user prod doesn't break before tokens
   are migrated.

3. **Dev** (both empty): auth bypassed entirely.

Exempt paths (health, OpenAPI docs) skip auth in all modes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Paths that are reachable without a bearer token.
DEFAULT_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/api/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)

# Match `/users/{user_id}/...` and `/api/users/{user_id}/...`.
_USER_PATH_RE = re.compile(r"^(?:/api)?/users/([^/]+)(?:/|$)")


def parse_tokens(raw: str) -> dict[str, str]:
    """Parse the `APP_TOKENS` JSON env var into a {token: user_id} map.

    Empty string returns {}. Malformed JSON raises ValueError so the
    failure is loud at app startup rather than silently disabling auth.
    """
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("APP_TOKENS must be a JSON object {token: user_id}")
    for token, user_id in parsed.items():
        if not isinstance(token, str) or not isinstance(user_id, str):
            raise ValueError("APP_TOKENS entries must be string→string")
        if not token or not user_id:
            raise ValueError("APP_TOKENS tokens and user_ids must be non-empty")
    return parsed


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Bearer-token auth with optional per-user-id path enforcement."""

    def __init__(
        self,
        app,  # type: ignore[no-untyped-def]
        token: str = "",
        tokens: dict[str, str] | None = None,
        exempt_paths: frozenset[str] = DEFAULT_EXEMPT_PATHS,
    ) -> None:
        super().__init__(app)
        self.token = token
        self.tokens = tokens or {}
        self.exempt_paths = exempt_paths

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Dev mode: nothing configured → bypass.
        if not self.token and not self.tokens:
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

        # Multi-user mode takes precedence when configured.
        if self.tokens:
            bound_user = self.tokens.get(provided)
            if bound_user is None:
                return JSONResponse({"detail": "Invalid token"}, status_code=401)
            path_user = _path_user_id(request.url.path)
            if path_user is not None and path_user != bound_user:
                return JSONResponse(
                    {"detail": "Token not authorized for this user"},
                    status_code=403,
                )
            return await call_next(request)

        # Legacy single-token mode: no path enforcement.
        if provided != self.token:
            return JSONResponse({"detail": "Invalid token"}, status_code=401)
        return await call_next(request)


def _path_user_id(path: str) -> str | None:
    match = _USER_PATH_RE.match(path)
    return match.group(1) if match else None
