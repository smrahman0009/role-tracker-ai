"""Pydantic request/response models for the API.

These get filled in incrementally as routes land. See docs/api_spec.md
for the full set planned. Domain models like SavedQuery are imported
from their domain modules — we don't duplicate them here.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from role_tracker.queries.models import SavedQuery
from role_tracker.resume.models import ResumeMetadata

__all__ = [
    "ApiError",
    "CreateQueryRequest",
    "CritiqueScore",
    "GenerateLetterRequest",
    "GenerateLetterResponse",
    "HealthResponse",
    "HiddenListsResponse",
    "JobDetailResponse",
    "JobListResponse",
    "JobSummary",
    "Letter",
    "LetterGenerationStatus",
    "LetterVersionList",
    "ManualEditRequest",
    "ProfileResponse",
    "QueryListResponse",
    "RefineLetterRequest",
    "RefreshJobResponse",
    "RefreshStatusResponse",
    "ResumeMetadata",
    "SavedQuery",
    "SearchJobsRequest",
    "SearchJobsResponse",
    "Strategy",
    "UpdateHiddenListRequest",
    "UpdateProfileRequest",
    "UpdateQueryRequest",
    "ApplicationListResponse",
    "ApplicationSummary",
    "FetchJobUrlRequest",
    "FetchJobUrlResponse",
    "ManualJobRequest",
    "MarkAppliedRequest",
    "PolishLetterRequest",
    "PolishLetterResponse",
    "PolishWhyInterestedRequest",
    "WhyInterestedResponse",
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


# ----- Jobs -----

JobFilter = Literal["all", "unapplied", "applied"]


class JobSummary(BaseModel):
    """Slim job shape for list views — no full description."""

    job_id: str
    title: str
    company: str
    location: str
    posted_at: str
    salary_min: float | None = None
    salary_max: float | None = None
    publisher: str
    url: str
    match_score: float
    fit_assessment: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    applied: bool = False
    description_preview: str


class JobListResponse(BaseModel):
    """Body of GET /users/{user_id}/jobs."""

    jobs: list[JobSummary]
    total: int                          # count after all filters
    total_unfiltered: int = 0           # count before query-param filters
    hidden_by_filters: int = 0          # = total_unfiltered - total
    last_refreshed_at: datetime | None
    next_refresh_allowed_at: datetime | None = None
    # Pipeline transparency — surfaced in the UI subtitle so users
    # understand "10 of 247 candidates kept" rather than seeing an
    # opaque list. Filled in by the refresh; 0 between refreshes.
    candidates_seen: int = 0            # pre-rank, post-hidden-list
    queries_run: int = 0                # number of saved searches fanned out
    top_n_cap: int = 0                  # the user's top_n_jobs setting at refresh time


class JobDetailResponse(BaseModel):
    """Body of GET /users/{user_id}/jobs/{job_id} — full JD included."""

    job_id: str
    title: str
    company: str
    location: str
    posted_at: str
    salary_min: float | None = None
    salary_max: float | None = None
    publisher: str
    url: str
    description: str
    match_score: float
    fit_assessment: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    applied: bool = False


class RefreshJobResponse(BaseModel):
    """Body of POST /users/{user_id}/jobs/refresh — returned 202 immediately."""

    refresh_id: str
    status: Literal["pending"]


class RefreshStatusResponse(BaseModel):
    """Body of GET /users/{user_id}/jobs/refresh/{refresh_id}.

    Also used for /jobs/search/{search_id} — same shape, same lifecycle.
    The frontend treats them identically; only the kickoff endpoint differs.
    """

    refresh_id: str
    status: Literal["pending", "running", "done", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    jobs_added: int | None = None
    candidates_seen: int | None = None
    queries_run: int | None = None
    error: str | None = None


class SearchJobsRequest(BaseModel):
    """Body of POST /users/{user_id}/jobs/search.

    Ad-hoc search spec. `what` is a list of role terms (1-3) — each runs
    its own JSearch query and results are merged + deduped + ranked
    against the resume. `where` is a single free-text location string;
    JSearch hands it to Google for Jobs which resolves geo naturally
    ("Halifax, Canada", "Toronto, ON", "Remote", etc.). Other fields
    are optional refinements that mirror the chip-filter shape.

    Cap of 3 terms keeps the JSearch quota cost bounded — each search
    costs `2 * len(what)` requests at limit_per_query=20.
    """

    what: list[str] = Field(min_length=1, max_length=3)
    # Up to 3 locations. Each (what × where) combination becomes its
    # own JSearch query, so 3×3=9 calls max per search. Free tier (200
    # calls/month) absorbs ~22 such searches.
    where: list[str] = Field(min_length=1, max_length=3)
    salary_min: int | None = Field(default=None, ge=0)
    employment_types: list[
        Literal["FULLTIME", "PARTTIME", "CONTRACTOR", "INTERN"]
    ] = []
    posted_within_days: int | None = Field(default=None, ge=1, le=365)
    # Optional per-search override for the ranking cap. None falls back
    # to the user's profile default (UserProfile.top_n_jobs).
    top_n: int | None = Field(default=None, ge=1, le=200)


class MarkAppliedRequest(BaseModel):
    """Body of POST /jobs/{job_id}/applied — captures what the user
    sent at the moment they clicked Mark Applied. All fields optional;
    backend snapshots resume metadata server-side regardless of body."""

    letter_version_used: int | None = None


class ApplicationSummary(BaseModel):
    """My Applications card shape — JobSummary plus the rich record
    captured at apply time."""

    job: JobSummary
    applied_at: datetime | None = None
    resume_filename: str = ""
    resume_sha256: str = ""
    letter_version_used: int | None = None
    # `True` when the resume currently on file has a different sha256
    # from the snapshot — meaning the user replaced their resume after
    # applying. The frontend uses this to render a "now replaced" tag.
    resume_replaced_since: bool = False


class ApplicationListResponse(BaseModel):
    """Body of GET /jobs/applications."""

    applications: list[ApplicationSummary]
    total: int


class FetchJobUrlRequest(BaseModel):
    """Body of POST /jobs/manual/fetch — convenience for the Add Job
    Manually dialog. Tries to extract title/company/description from the
    URL using Trafilatura; returns empty strings on any failure so the
    frontend can fall back to user-paste."""

    url: str = Field(min_length=8, max_length=2000)


class FetchJobUrlResponse(BaseModel):
    """Whatever we managed to pull from the URL. Any field may be empty
    (extraction is best-effort; caller treats empty `description` as a
    signal to ask the user to paste it themselves)."""

    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""


class ManualJobRequest(BaseModel):
    """Body of POST /jobs/manual — create a job from a URL the user
    found themselves.

    `description` is required (the agent needs JD text to write a letter
    against). `url` is optional — if provided, it's persisted as the
    job's link so the View posting button works on the detail page.
    """

    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=50, max_length=20_000)
    location: str = ""
    url: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    employment_type: str = ""


class SearchJobsResponse(BaseModel):
    """Body of POST /users/{user_id}/jobs/search — returned 202 immediately.

    Frontend polls /jobs/search/{search_id} (RefreshStatusResponse shape)
    until status="done", then re-fetches /jobs to render the results.
    """

    search_id: str
    status: Literal["pending"]


# ----- Cover letters -----


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
    notes: str = ""


class Letter(BaseModel):
    """One version of a saved cover letter (response shape)."""

    version: int
    text: str
    word_count: int
    strategy: Strategy | None = None
    critique: CritiqueScore | None = None
    feedback_used: str | None = None
    refinement_index: int = 0       # 0 for original, 1..10 for refines
    edited_by_user: bool = False    # true if user manually edited
    created_at: datetime


class LetterVersionList(BaseModel):
    """Body of GET /users/{user_id}/jobs/{job_id}/letters."""

    versions: list[Letter]              # latest first
    total: int


class GenerateLetterRequest(BaseModel):
    """Body of POST /users/{user_id}/jobs/{job_id}/letters.

    All fields optional. Empty body = identical behaviour to the
    one-click Generate button (the original contract). Filled fields
    come from the GenerateLetterDialog (docs/cover_letter_dialog_plan.md).
    """

    # User-supplied steering ("make it punchy, mention my fintech work").
    # Threaded into the agent's system prompt as high-priority guidance.
    instruction: str | None = Field(default=None, max_length=500)

    # An existing letter to mirror in voice, length, and structure.
    # Content stays grounded in the user's resume + this JD; only the
    # *style* is borrowed from the template.
    template: str | None = Field(default=None, max_length=4_000)

    # Anthropic's extended-thinking mode. Higher quality on non-obvious
    # resume↔JD matches at ~2-3× cost and 2-3× latency. Off by default.
    extended_thinking: bool = False


class GenerateLetterResponse(BaseModel):
    """Returned 202 immediately from generate / regenerate / refine."""

    generation_id: str
    status: Literal["pending"]
    estimated_seconds: int = 60


class LetterGenerationStatus(BaseModel):
    """Body of GET /users/{user_id}/letter-jobs/{generation_id}."""

    generation_id: str
    status: Literal["pending", "running", "done", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    letter: Letter | None = None        # populated when status="done"
    error: str | None = None
    # Human-readable progress label, updated by the agent at each
    # tool-call iteration. Frontend renders it under the spinner.
    phase: str = "Starting…"


class RefineLetterRequest(BaseModel):
    """Body of POST /users/{user_id}/jobs/{job_id}/letters/{version}/refine."""

    feedback: str = Field(min_length=5, max_length=500)

    # Same toggle as GenerateLetterRequest — extended thinking on the
    # refine call instead of the generate call. Useful when the user
    # wants the agent to think hard about a tricky correction.
    extended_thinking: bool = False


class ManualEditRequest(BaseModel):
    """Body of POST /users/{user_id}/jobs/{job_id}/letters/{version}/edit.

    Validation here is gentler than the agent's hard limits — users get
    more freedom than the agent does. The deterministic checks
    (word count 200-500, paragraph length ≤ 200 words) live in the
    route, not the schema, since they require splitting the text.
    """

    text: str = Field(min_length=1, max_length=5000)


# ----- Profile (contact info + show-in-letter flags) -----


class ProfileResponse(BaseModel):
    """Body of GET /users/{user_id}/profile."""

    name: str
    phone: str = ""
    email: str = ""
    city: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""

    show_phone_in_header: bool = True
    show_email_in_header: bool = True
    show_city_in_header: bool = True
    show_linkedin_in_header: bool = True
    show_github_in_header: bool = True
    show_portfolio_in_header: bool = True

    # How many ranked matches the refresh pipeline keeps. Higher = more
    # browsing freedom but more low-similarity jobs. Capped at 200 to
    # prevent accidental huge refreshes.
    top_n_jobs: int = Field(default=50, ge=1, le=200)


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

    top_n_jobs: int | None = Field(default=None, ge=1, le=200)


# ----- Hidden lists -----


class WhyInterestedResponse(BaseModel):
    """Body of the why-interested generator response."""

    text: str
    word_count: int


class PolishLetterRequest(BaseModel):
    """Body of POST /jobs/{job_id}/letters/{version}/polish.

    Cleans grammar and clarity in user-edited cover letter text without
    changing meaning, length, or structure (paragraphs, bold markers,
    link syntax all preserved).
    """

    text: str = Field(min_length=20, max_length=10_000)


class PolishLetterResponse(BaseModel):
    """Body of the cover-letter polish response."""

    text: str
    word_count: int


class PolishWhyInterestedRequest(BaseModel):
    """Body of POST /jobs/{job_id}/why-interested/polish.

    Fixes grammar / clarity in user-edited why-interested text without
    changing meaning or length.
    """

    text: str = Field(min_length=10, max_length=2000)


class HiddenListsResponse(BaseModel):
    """Body of GET /users/{user_id}/hidden.

    Publishers were dropped from the per-user response when the
    hidden-publishers list became a single admin-managed global —
    fetch via GET /global/hidden-publishers instead.
    """

    companies: list[str]
    title_keywords: list[str]


class UpdateHiddenListRequest(BaseModel):
    """Body of PUT /users/{user_id}/hidden/{kind}.

    Replace-style: send the full list each time. To clear, send
    {"items": []}.
    """

    items: list[str]


class FeatureCount(BaseModel):
    """Per-feature call count + estimated cost for the Usage page."""

    feature: str
    count: int
    estimated_cost_usd: float


class UsageMonth(BaseModel):
    """One month's usage rollup for a single user."""

    year_month: str
    jsearch_calls: int
    feature_calls: list[FeatureCount]
    estimated_anthropic_cost_usd: float
    estimated_openai_cost_usd: float
    estimated_total_cost_usd: float


class UsageResponse(BaseModel):
    """Body of GET /users/{user_id}/usage.

    Returns the current month plus up to 5 prior months (newest first).
    """

    current: UsageMonth
    history: list[UsageMonth] = []


ModelChoice = Literal["haiku", "sonnet"]


class CoverLetterAnalysisRequest(BaseModel):
    """Body of POST /users/{user_id}/jobs/{job_id}/cover-letter/analysis.

    Sonnet by default. Haiku selectable per call for a cheaper run.
    """

    model: ModelChoice = "sonnet"


class CoverLetterAnalysisResponse(BaseModel):
    """Body returned by the match-analysis route.

    Four short bullet lists comparing the user's resume to the JD,
    plus the model that produced them (so the UI can show "Analysis
    by claude-sonnet-4-6" etc.).
    """

    strong: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    partial: list[str] = Field(default_factory=list)
    excitement_hooks: list[str] = Field(default_factory=list)
    model: str


class CoverLetterSummaryRequest(BaseModel):
    """Body of POST /users/{user_id}/jobs/{job_id}/cover-letter/summary.

    Sonnet by default because the summary is creative prose; Haiku
    is available for cost-vs-quality comparison.
    """

    model: ModelChoice = "sonnet"


class CoverLetterSummaryResponse(BaseModel):
    """Three-section JD digest. Any field can be "" if the JD does
    not say anything genuine about it; the frontend skips rendering
    empty sections instead of padding the response with fluff."""

    role: str = ""
    requirements: str = ""
    context: str = ""
    model: str
