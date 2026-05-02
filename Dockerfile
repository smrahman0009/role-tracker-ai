# syntax=docker/dockerfile:1.7

# ---------- Stage 1: build the frontend ----------
FROM node:20-slim AS frontend-builder

WORKDIR /build

# Install deps with a clean, lockfile-driven install. Copy only the
# manifest first so npm's layer caches when source code changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy the rest of the frontend source and build.
COPY frontend/ ./
RUN npm run build


# ---------- Stage 2: install Python deps ----------
FROM python:3.12-slim AS python-deps

# uv is a fast, lockfile-aware Python package manager. We install it
# once into the image and use it to install our deps into a venv.
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cacheable) — only re-runs when
# pyproject.toml or uv.lock changes. We export the locked deps to
# requirements.txt so `uv pip install` does the work — this is more
# predictable than `uv sync` when we're not installing the project.
COPY pyproject.toml uv.lock ./
RUN uv venv /opt/venv && \
    uv export --frozen --no-dev --no-emit-project --format requirements-txt \
        > /tmp/requirements.txt && \
    VIRTUAL_ENV=/opt/venv uv pip install --no-cache -r /tmp/requirements.txt

# Now copy the source and install the project itself (no deps —
# they're already in the venv from the previous layer).
COPY src/ ./src/
COPY README.md ./
RUN VIRTUAL_ENV=/opt/venv uv pip install --no-cache --no-deps .


# ---------- Stage 3: runtime image ----------
FROM python:3.12-slim AS runtime

# Non-root user — never run web servers as root in production.
RUN groupadd -r app && useradd -r -g app -u 1000 app

WORKDIR /app

# Bring in the prepared venv and the compiled frontend bundle.
COPY --from=python-deps /opt/venv /opt/venv
COPY --from=frontend-builder /build/dist ./frontend/dist

# Source code (already installed into the venv, but kept on disk for
# clear stack traces and to mirror the dev layout).
COPY src/ ./src/
COPY users/ ./users/
COPY config.yaml ./

# Where mutable per-user data lives. Mount a volume here in production
# (Azure Files / a managed disk) so resumes, applied records, letters,
# and usage rollups survive container restarts.
RUN mkdir -p /app/data && chown -R app:app /app

USER app

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FRONTEND_DIST=/app/frontend/dist \
    API_HOST=0.0.0.0 \
    API_PORT=8000

EXPOSE 8000

# Lightweight liveness check — the API's health endpoint is mounted
# under /api/ in the production app.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
    sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status == 200 else 1)"

CMD ["uvicorn", "role_tracker.api.production:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
