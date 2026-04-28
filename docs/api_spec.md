# Role Tracker — API Specification

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

### API field names vs user-facing labels
The API uses internal field names like `exclude_companies`,
`exclude_title_keywords`, `exclude_publishers` — these are stable
contracts and carry over from the existing domain model. The
**user-facing UI labels these as "Hidden companies", "Hidden title
keywords", "Hidden publishers"** — neutral framing that reads as
personal filtering preference rather than a public judgment about
named entities.

When working on the frontend, always use the "Hidden" naming in
labels, descriptions, and copy. When working on the backend or API,
the `exclude_*` field names are unchanged.

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
List ranked job matches from the latest cached snapshot.

**Query parameters (all optional):**

| Param                | Type / format                                   | Behavior                                                                |
|----------------------|--------------------------------------------------|-------------------------------------------------------------------------|
| `filter`             | `all` \| `unapplied` (default) \| `applied`     | Single-select. Filters by the `applied` flag.                           |
| `type`               | comma-separated string                          | Multi-value. OR-logic on job title containing any term, case-insensitive. |
| `location`           | comma-separated string                          | Multi-value. OR-logic on job location containing any term.              |
| `salary_min`         | integer (CAD)                                   | Drops jobs whose `salary_min` is below this. See `hide_no_salary` below. |
| `hide_no_salary`     | `true` \| `false` (default `false`)             | If true, also hide jobs without a salary listed (only meaningful with `salary_min`). |
| `employment_types`   | comma-separated `FULLTIME,PARTTIME,CONTRACTOR,INTERN` | Multi-value. OR-logic. Maps to JSearch's `job_employment_type` field. |
| `posted_within_days` | integer (typically 7, 30, 90)                   | Single-select. Drops jobs older than N days based on `posted_at`.       |

**Filter logic across params:** AND between filter types, OR within each
multi-value filter. Example:

```
GET /users/smrah/jobs?
    filter=unapplied&
    type=Data%20Scientist,ML%20Engineer&
    location=Toronto,Remote&
    salary_min=80000&
    employment_types=FULLTIME,CONTRACTOR&
    posted_within_days=30
```

A job matches if: it's unapplied AND its title contains "data scientist"
OR "ml engineer", AND its location contains "toronto" OR "remote", AND
its `salary_min ≥ 80000`, AND its employment type is FULLTIME OR
CONTRACTOR, AND it was posted within the last 30 days.

URL state is the source of truth: the frontend reflects active filters
in the query string so refresh, back/forward, and link-sharing work.

**Response 200:** `JobListResponse` — contains the filtered list plus a
`hidden_by_filters` count so the UI can show "Showing N of M jobs · K
hidden by your filters".

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
generation_id to poll.

**The refinement strictly preserves the committed strategy** (primary
project, narrative angle, fit assessment). It can only revise prose,
voice, length, emphasis within sentences. It cannot switch the primary
project or change the narrative angle. If the user's feedback implies
a strategy change ("focus on the audio ML angle instead of NLP"), the
refinement will produce a same-strategy letter that mostly ignores the
implied change. To actually change strategy, the user must call
`POST /jobs/{job_id}/regenerate` (below).

This is by design — refinement that drifts the strategy round by round
loses the anchor that makes letters coherent.

**Per-letter refinement cap:** each letter has a hard limit of 10
refinements. After the 10th refine call on a given letter (counting
across the whole version history that traces back to the same original
generation), this endpoint returns:

- **Response 422:** `{"detail": "10 refinements is the cap for this
  letter. Regenerate (POST /jobs/{id}/regenerate) for a fresh
  approach."}` with the body shape:

```python
class Letter(BaseModel):
    ...
    refinement_index: int = 0   # 0 for the original generation,
                                 # 1..10 for refined versions
```

Quality drift past 10 rounds is real — the cleanest path is a fresh
strategy via regenerate, not refine #11. The frontend should show a
counter ("Refinement 4 of 10") and disable the refine button at 10.

**Request body:** `RefineLetterRequest`
**Response 202:** `GenerateLetterResponse`
**Response 422:** if the per-letter refinement cap is exceeded.

#### `POST /users/{user_id}/jobs/{job_id}/letters/{version}/edit`
Save a manually-edited version of a letter. Synchronous (no agent
involvement, no background task). The user's text is taken as-is and
saved as a new version in the same job's history.

**The committed strategy carries forward unchanged** to the new
version, but `critique` is set to `null` because the agent's quality
assessment doesn't apply to text the agent didn't write. The frontend
displays edited versions with a "Edited by you" label instead of the
critique badge.

**Request body:** `ManualEditRequest`
**Response 201:** `Letter` — the new version (with `feedback_used =
"manual edit"`).
**Response 422:** if the text is empty, > 5000 chars, or fails the
deterministic checks (word count outside 200-500, paragraph > 200
words). Validation is gentler than the agent's hard limits — users
get more freedom than the agent does.

This endpoint does NOT count toward the 10-refinement cap, the daily
20-generation rate limit, or any other quota. Manual edits are free.

#### `POST /users/{user_id}/jobs/{job_id}/regenerate`
Throw away the existing strategy and start over from scratch. Async —
returns a new generation_id. Use this when the existing letter is on
the wrong track and refinement won't help.

The agent re-reads the JD, re-fetches resume sections, picks a new
strategy (which may pick a different primary project, different angle,
or different fit assessment), drafts, critiques, and saves. The new
letter becomes a new version; previous versions are kept.

**Request body:** none.
**Response 202:** `GenerateLetterResponse`
**Response 429:** if daily rate limit hit (regenerate counts toward
the same 20/day limit as initial generation).

#### `GET /users/{user_id}/jobs/{job_id}/letters/{version}/download.md`
Download the letter as a Markdown file.

**Response 200:** `text/markdown` body.

#### PDF download — handled in the browser, not the backend

Server-side PDF rendering was deferred out of MVP scope after the final
plan review. The risk of WeasyPrint / system-font issues on Azure App
Service Linux F1 is real and could eat half a day in Phase 8. Reportlab
output looks notably worse than WeasyPrint's.

**MVP approach:** the frontend renders the letter as nicely formatted HTML
and the user clicks "Print → Save as PDF" in their browser. One click,
zero backend complexity, identical-looking PDF.

If, after Phase 9 ships, server-side PDF turns out to add real value
(automated email attachments, server-rendered share links), we revisit.

---

### 5. Saved queries

The user's job-search queries (what + where) live in Cosmos DB and are
editable from the UI. On first run, the backend bootstraps from
`users/{id}.yaml`; after that, the YAML is ignored and the DB is the
source of truth.

#### `GET /users/{user_id}/queries`
List all saved queries for this user.

**Response 200:** `QueryListResponse`

#### `POST /users/{user_id}/queries`
Add a new query. **Auto-triggers a job refresh** (subject to the
60-second throttle below).

**Request body:** `CreateQueryRequest`
**Response 201:** `SavedQuery` — newly created.
**Side effect:** kicks off a background refresh if cooldown allows.

#### `PUT /users/{user_id}/queries/{query_id}`
Update an existing query (change `what`, `where`, or `enabled`).
**Auto-triggers a job refresh** (subject to throttle).

**Request body:** `UpdateQueryRequest` (all fields optional)
**Response 200:** `SavedQuery` — updated.
**Side effect:** kicks off a background refresh if cooldown allows.

#### `DELETE /users/{user_id}/queries/{query_id}`
Remove a query. Does NOT auto-refresh (less work, not more).

**Response 204:** no body.

#### Refresh throttle

To prevent JSearch quota burn during rapid query edits, the backend
enforces a **60-second cooldown** on auto-refreshes. If a query
change happens within 60s of the last refresh, the change is saved
to the DB immediately but the refresh is **deferred** until the
cooldown expires OR the user clicks "Refresh jobs" manually. The
`/jobs` endpoint includes `next_refresh_allowed_at` so the frontend
can display a "next auto-refresh in N seconds" banner.

This applies only to auto-refreshes triggered by query CRUD; manual
refreshes via `POST /jobs/refresh` ignore the cooldown.

---

### 6. Apply tracking

#### `POST /users/{user_id}/jobs/{job_id}/applied`
Mark this job as applied. Hides it from the default job list view.

**Response 204:** no body.
**Response 409:** if already marked.

#### `DELETE /users/{user_id}/jobs/{job_id}/applied`
Unmark applied. Job returns to the unapplied list.

**Response 204:** no body.

---

### 7. Profile (contact info shown in cover letters)

#### `GET /users/{user_id}/profile`
Return the user's contact info plus the per-field "show in letter"
flags. Used by the Settings → Contact info form.

**Response 200:** `ProfileResponse`

#### `PUT /users/{user_id}/profile`
Update contact info and/or per-field show-in-letter flags. All fields
optional — only the ones provided get patched.

**Request body:** `UpdateProfileRequest`
**Response 200:** `ProfileResponse` — the updated profile.

The agent's letter-header builder respects these flags:

- Empty field OR `show_in_header=false` → that line is skipped
- Filled field AND `show_in_header=true` → that line appears

Name is always shown. Email/phone/city/LinkedIn/GitHub/portfolio are
each individually toggleable.

---

### 8. Hidden lists (filter preferences)

These three endpoints manage the user's personal filter lists. The
field names use `exclude_*` for backward compatibility with the existing
domain model, but the UI labels them "Hidden" — the API name is just an
internal identifier.

#### `GET /users/{user_id}/hidden`
Return all three hidden lists in one response.

**Response 200:** `HiddenListsResponse` —
```python
{
  "companies": ["bank", "insurance", ...],
  "title_keywords": ["banking", "wealth", ...],
  "publishers": ["...", ...]   # may be empty
}
```

#### `PUT /users/{user_id}/hidden/companies`
Replace the entire `exclude_companies` list. Useful for both bulk
edits and the "Clear all" button (send `{"items": []}`).

**Request body:** `{"items": ["string", ...]}`
**Response 200:** the updated list.

#### `PUT /users/{user_id}/hidden/title-keywords`
Same pattern for `exclude_title_keywords`.

#### `PUT /users/{user_id}/hidden/publishers`
Same pattern for `exclude_publishers`.

For granular add/remove the UI can fetch the current list, modify
locally, and PUT the new list back. Three small dedicated CRUD endpoints
per list felt like overkill for stable data the user touches rarely.

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
    total: int                          # count of jobs in this response
    total_unfiltered: int                # before query-param filters
    hidden_by_filters: int               # total_unfiltered - total
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

# ---------- Saved queries ----------

class SavedQuery(BaseModel):
    query_id: str           # short UUID
    what: str               # job type, e.g. "data scientist", "ML engineer"
    where: str              # location, e.g. "canada", "toronto", "remote"
    enabled: bool = True    # disable without deleting
    created_at: datetime

class QueryListResponse(BaseModel):
    queries: list[SavedQuery]
    next_refresh_allowed_at: datetime | None  # for auto-refresh throttle

class CreateQueryRequest(BaseModel):
    what: str
    where: str

class UpdateQueryRequest(BaseModel):
    what: str | None = None
    where: str | None = None
    enabled: bool | None = None

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

class ManualEditRequest(BaseModel):
    """Body of POST /jobs/{job_id}/letters/{version}/edit."""
    text: str                           # full letter Markdown, 1-5000 chars

# ---------- Profile (contact info + show-in-letter flags) ----------

class ProfileResponse(BaseModel):
    """Body of GET /users/{user_id}/profile."""

    # Identity (always shown in letter header if set)
    name: str

    # Optional fields, each individually toggleable
    phone: str = ""
    email: str = ""
    city: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""              # NEW: optional personal site/portfolio

    # Per-field "show in letter header" flags. All default True.
    # Empty fields are skipped regardless of flag (you can't render blank).
    show_phone_in_header: bool = True
    show_email_in_header: bool = True
    show_city_in_header: bool = True
    show_linkedin_in_header: bool = True
    show_github_in_header: bool = True
    show_portfolio_in_header: bool = True


class UpdateProfileRequest(BaseModel):
    """Body of PUT /users/{user_id}/profile. All fields optional."""

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None

    show_phone_in_header: bool | None = None
    show_email_in_header: bool | None = None
    show_city_in_header: bool | None = None
    show_linkedin_in_header: bool | None = None
    show_github_in_header: bool | None = None
    show_portfolio_in_header: bool | None = None


# ---------- Hidden lists ----------

class HiddenListsResponse(BaseModel):
    """Body of GET /users/{user_id}/hidden."""
    companies: list[str]
    title_keywords: list[str]
    publishers: list[str]


class UpdateHiddenListRequest(BaseModel):
    """Body of PUT /users/{user_id}/hidden/{kind}.

    Replace-style: send the full list each time. To clear, send
    {"items": []}.
    """
    items: list[str]
```

The existing `Letter` shape gets one new field:

```python
class Letter(BaseModel):
    version: int
    text: str
    word_count: int
    strategy: Strategy | None = None
    critique: CritiqueScore | None = None
    feedback_used: str | None = None
    refinement_index: int = 0           # 0 for original generation,
                                         # 1..10 for refined versions,
                                         # carries through manual edits
    edited_by_user: bool = False         # true if last save was a manual edit
    created_at: datetime
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
single-user scale. No Celery / queue worker needed at this size.

### Stale-task sweeper (important)

App Service F1 sleeps after 20 min idle and can be restarted by Azure
at any time. If a background task is running when this happens, the
in-memory work dies but its poll record remains in Cosmos DB stuck on
`status="running"` forever. Without protection, the frontend would
poll forever and the user would never see an error.

**Rule:** any poll record with `status="running"` and `started_at >
5 minutes ago` is a dead task. Two implementation options:

1. **On every poll request,** check `started_at` first. If older than
   5 minutes and still `running`, mark `failed` with
   `error="Generation timed out (likely server restart). Please retry."`
   and return that. Cheap, no separate scheduler needed.
2. **A periodic sweep** (every 60s via FastAPI's lifespan / startup)
   marks all stale records as failed.

Recommendation: implement (1) — it's lazy, free, and self-cleaning.
Same logic for `refresh_id` records.

The 5-minute cutoff is generous (a normal generation finishes in
30-60 seconds) so it won't mark in-flight work as failed.

---

## What's intentionally NOT in the API yet

The following will be added in later phases when we hit the use case:

- **Search / filter on jobs** beyond `applied/unapplied` (e.g. by company,
  by date) — only when we have enough jobs to need it.
- **Bulk operations** (mark several as applied at once) — premature.
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
