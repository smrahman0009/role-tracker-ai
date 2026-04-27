# Role Tracker AI — API Specification

> **Phase 5 first deliverable.** This is the contract for the FastAPI
> backend. No backend code is written until this is approved.
>
> **Status:** draft, awaiting user review.
> **Branch:** `phase/5-web-app`.

---

## Conventions

### Base URL
- **Local dev:** `http://localhost:8000`
- **Production:** `https://<app-name>.azurewebsites.net`

### Authentication
Every endpoint except `/health` requires:

```
Authorization: Bearer <APP_TOKEN>
```

The token is a single long random string set in the backend's
`APP_TOKEN` environment variable. If the header is missing or wrong,
the server returns **`401 Unauthorized`**.

If `APP_TOKEN` is empty/unset (local dev), the middleware skips the
check entirely.

### User identity
Every per-user endpoint includes `user_id` in the URL path:
`/users/{user_id}/...`. For Phase 5-8, `user_id` is hardcoded to
`"smrah"` on the frontend. The backend does **not** assume any
particular user_id — it accepts whatever the URL path carries. This
keeps multi-user migration trivial later.

### Content type
- Requests: `application/json` for body, `multipart/form-data` for
  resume upload only.
- Responses: `application/json`, except PDF download which is
  `application/pdf`.

### Error response shape
Pydantic validation errors come from FastAPI in the standard format:

```json
{
  "detail": [
    {
      "loc": ["body", "feedback"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

Custom errors use a simpler shape:

```json
{ "detail": "Human-readable error message" }
```

### HTTP status codes
- `200` — success, body returned
- `201` — resource created
- `202` — async task accepted (used by letter generation)
- `204` — success, no body
- `400` — client error (bad request data)
- `401` — missing or wrong bearer token
- `404` — resource not found
- `409` — conflict (e.g., job already marked applied)
- `422` — Pydantic validation error
- `429` — rate limit hit
- `500` — server error

### Rate limiting
**20 cover-letter generations per user per day.** When exceeded, the
generation endpoint returns `429` with a `Retry-After` header. Other
endpoints have no rate limits.

---

## Endpoints

### 1. Health check

#### `GET /health`
**No auth required.** Returns 200 if backend is alive. Used by Azure
App Service liveness probes.

**Response 200:**
```json
{ "status": "ok", "version": "0.1.0" }
```

---

### 2. Resume

#### `POST /users/{user_id}/resume`
Upload (or replace) the user's resume PDF.

**Request:** `multipart/form-data` with a `file` field containing a
single PDF (max 5 MB).

**Response 201:** `ResumeMetadata`

**Errors:** 400 if not a PDF, 413 if >5 MB.

#### `GET /users/{user_id}/resume`
Get metadata about the currently-stored resume (does NOT return the
file itself).

**Response 200:** `ResumeMetadata`
**Response 404:** if no resume uploaded yet.

#### `GET /users/{user_id}/resume/file`
Download the original PDF.

**Response 200:** `application/pdf` body.

---

### 3. Jobs

#### `GET /users/{user_id}/jobs`
List ranked job matches. Returns from cache if a refresh hasn't been
triggered; otherwise runs the matching pipeline.

**Query parameters:**
- `filter` (optional, default `unapplied`): one of `all`, `unapplied`,
  `applied`. Controls which jobs are returned.

**Response 200:** `JobListResponse`

#### `POST /users/{user_id}/jobs/refresh`
Force re-fetch from JSearch and re-rank. Slow (~30-90 seconds).
Async — returns a generation ID to poll.

**Response 202:** `RefreshJobResponse`

#### `GET /users/{user_id}/jobs/refresh/{refresh_id}`
Poll the status of a job-refresh operation.

**Response 200:** `RefreshStatusResponse`

#### `GET /users/{user_id}/jobs/{job_id}`
Get a single job's full details, including JD text, match score, and
applied flag.

**Response 200:** `JobDetailResponse`
**Response 404:** if `job_id` not in this user's cache.

---

### 4. Cover letters

The generation flow is **async with polling**, because Sonnet 4.6 + the
agent loop takes 30-60 seconds.

#### `POST /users/{user_id}/jobs/{job_id}/letters`
Kick off cover-letter generation for the given job.

**Request body:** `GenerateLetterRequest` (currently empty — reserved
for future fields like `extra_instructions`).

**Response 202:** `GenerateLetterResponse` — contains a
`generation_id` to poll.
**Response 429:** if daily rate limit hit.

#### `GET /users/{user_id}/letter-jobs/{generation_id}`
Poll the status of a letter generation. Used by the frontend every
2-3 seconds while a letter is being written.

**Response 200:** `LetterGenerationStatus`

When `status == "done"`, the response includes the full letter,
strategy, and critique. When `status == "failed"`, includes an
`error` field with a short reason.

#### `GET /users/{user_id}/jobs/{job_id}/letters`
List all letter versions saved for this job (latest first).

**Response 200:** `LetterVersionList`

#### `GET /users/{user_id}/jobs/{job_id}/letters/{version}`
Get a specific saved letter version (full text, strategy, critique).

**Response 200:** `Letter`
**Response 404:** if version doesn't exist.

#### `POST /users/{user_id}/jobs/{job_id}/letters/{version}/refine`
Refine a saved letter using free-text feedback. Async — returns a new
generation_id to poll. The refinement preserves the original strategy
and grounding rules.

**Request body:** `RefineLetterRequest`
**Response 202:** `GenerateLetterResponse`

#### `GET /users/{user_id}/jobs/{job_id}/letters/{version}/download.md`
Download the letter as a Markdown file.

**Response 200:** `text/markdown` body.

#### `GET /users/{user_id}/jobs/{job_id}/letters/{version}/download.pdf`
Server-rendered PDF of the letter. Generated on first request, then
cached.

**Response 200:** `application/pdf` body.

---

### 5. Apply tracking

#### `POST /users/{user_id}/jobs/{job_id}/applied`
Mark this job as applied. Hides it from the default job list view.

**Response 204:** no body.
**Response 409:** if already marked.

#### `DELETE /users/{user_id}/jobs/{job_id}/applied`
Unmark applied. Job returns to the unapplied list.

**Response 204:** no body.

---

## Pydantic models (request/response shapes)

These will live in `src/role_tracker/api/schemas.py`. The existing
domain models (`JobPosting`, `UserProfile`) are reused where useful.

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# ---------- Shared ----------

class ApiError(BaseModel):
    detail: str

# ---------- Resume ----------

class ResumeMetadata(BaseModel):
    filename: str
    size_bytes: int
    uploaded_at: datetime
    sha256: str  # used to detect when re-embedding is needed

# ---------- Jobs ----------

JobFilter = Literal["all", "unapplied", "applied"]

class JobSummary(BaseModel):
    """Slim version for list views — no full description."""
    job_id: str
    title: str
    company: str
    location: str
    posted_at: str
    salary_min: float | None = None
    salary_max: float | None = None
    publisher: str
    url: str
    match_score: float                  # 0.0 to 1.0
    fit_assessment: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    applied: bool = False
    description_preview: str            # first ~200 chars of JD

class JobListResponse(BaseModel):
    jobs: list[JobSummary]
    total: int
    last_refreshed_at: datetime | None
    next_refresh_allowed_at: datetime | None  # to throttle JSearch usage

class JobDetailResponse(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    posted_at: str
    salary_min: float | None = None
    salary_max: float | None = None
    publisher: str
    url: str
    description: str                    # full JD
    match_score: float
    fit_assessment: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    applied: bool

class RefreshJobResponse(BaseModel):
    refresh_id: str
    status: Literal["pending"]

class RefreshStatusResponse(BaseModel):
    refresh_id: str
    status: Literal["pending", "running", "done", "failed"]
    started_at: datetime
    completed_at: datetime | None
    jobs_added: int | None              # populated when status==done
    error: str | None = None            # populated when status==failed

# ---------- Cover letters ----------

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
    notes: str

class Letter(BaseModel):
    version: int                        # 1, 2, 3, ...
    text: str                           # full letter Markdown
    word_count: int
    strategy: Strategy
    critique: CritiqueScore
    created_at: datetime
    feedback_used: str | None = None    # populated for refined versions

class LetterVersionList(BaseModel):
    versions: list[Letter]              # latest first
    total: int

class GenerateLetterRequest(BaseModel):
    pass                                # reserved for future fields

class GenerateLetterResponse(BaseModel):
    generation_id: str
    status: Literal["pending"]
    estimated_seconds: int = 60

class LetterGenerationStatus(BaseModel):
    generation_id: str
    status: Literal["pending", "running", "done", "failed"]
    started_at: datetime
    completed_at: datetime | None
    letter: Letter | None = None        # populated when status==done
    error: str | None = None            # populated when status==failed

class RefineLetterRequest(BaseModel):
    feedback: str                       # free-text, 5-500 chars
```

---

## Async generation flow (sequence)

```
Frontend                      Backend                    Agent
   │                             │                         │
   │ POST /letters               │                         │
   │ ───────────────────────────>│                         │
   │                             │ create job record       │
   │                             │ kick off background     │
   │                             │ task                    │
   │ <────── 202 generation_id ──│                         │
   │                             │ ──────────────────────> │
   │                             │                         │
   │ GET /letter-jobs/{id}       │                         │
   │ ───────────────────────────>│                         │
   │ <───── 200 status=running ──│                         │
   │                             │                         │
   │ (polls every 2-3s)          │                         │
   │                             │                  letter ready
   │                             │ <────────────────────── │
   │                             │ persist to DB+Blob      │
   │                             │                         │
   │ GET /letter-jobs/{id}       │                         │
   │ ───────────────────────────>│                         │
   │ <─── 200 status=done +      │                         │
   │      letter+strategy+critique                         │
```

The "background task" runs inside FastAPI's `BackgroundTasks` for
single-user scale. No Celery / queue worker needed at this size. If
the backend restarts mid-generation, the task is lost — the frontend
will see `status=failed` after a timeout, and the user can retry.

---

## What's intentionally NOT in the API yet

The following will be added in later phases when we hit the use case:

- **Search / filter on jobs** beyond `applied/unapplied` (e.g. by company,
  by date) — only when we have enough jobs to need it.
- **Bulk operations** (mark several as applied at once) — premature.
- **Queries CRUD** (changing the user's saved JSearch queries from the
  UI) — Phase 5-8 reads them from `users/{id}.yaml`; UI editing is a
  later iteration.
- **Multiple resume variants** — locked decision: single resume per user.
- **Real auth endpoints** (`/login`, `/logout`) — Phase 5-8 uses bearer
  token only.

---

## Open items for user review

Please confirm or push back on each:

1. **`/jobs/refresh` is async with a poll endpoint.** Same pattern as
   letter generation. Alternative: synchronous endpoint that blocks for
   30-90 seconds. Async is friendlier UX but slightly more complex.
   Recommendation: keep async.

2. **`fit_assessment` is `Literal["HIGH", "MEDIUM", "LOW"] | None`** —
   `None` for jobs whose letter hasn't been generated yet (we only know
   fit after the agent runs). The job-list page would show "—" or "Not
   assessed" in those rows.

3. **`description_preview` length** in `JobSummary` for the list page.
   Currently spec says "first ~200 chars". Recommendation: 240 chars
   ending at a word boundary.

4. **Letter version numbering.** Spec uses `1, 2, 3, ...`. Alternative:
   UUIDs. Numbers are more user-friendly for URLs and version compare;
   UUIDs avoid race conditions in multi-user. Recommendation: numbers
   for now; switch to UUIDs at multi-user time.

5. **PDF caching.** Spec generates on first request and caches. If the
   user re-generates a refined letter, the PDF gets regenerated. OK?

6. **`refresh_id` and `generation_id` lifetimes.** How long do we keep
   poll records around? Recommendation: 24 hours (Cosmos DB TTL).
   Long enough for slow page reloads, short enough not to clutter.

7. **CORS.** Frontend at one domain, backend at another. Lock CORS to
   the specific frontend domain in production, allow `localhost:5173`
   (Vite default) in dev. Standard practice.

Once you've reviewed and either approved each item or asked for
changes, I'll start implementing the FastAPI scaffolding.
