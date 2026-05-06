/**
 * TypeScript types mirroring the FastAPI Pydantic schemas.
 *
 * Hand-written for now — we may swap to OpenAPI codegen later, but
 * the API surface is small enough that maintenance burden is low.
 * Single source of truth: docs/api_spec.md (kept in sync with
 * src/role_tracker/api/schemas.py).
 *
 * Convention: keep field names IDENTICAL to the Pydantic models so
 * the wire format and the TS types match without any field renaming
 * in the fetch layer.
 */

// ---------- Shared ----------

export interface ApiError {
  detail: string;
}

export interface HealthResponse {
  status: string;
  version: string;
}

// ---------- Resume ----------

export interface ResumeMetadata {
  filename: string;
  size_bytes: number;
  uploaded_at: string; // ISO datetime
  sha256: string;
}

/** POST /resume returns metadata + the contact fields we auto-filled. */
export interface ResumeUploadResponse extends ResumeMetadata {
  prefilled_fields: string[];
}

// ---------- Jobs ----------

export type JobFilter = "all" | "unapplied" | "applied";
export type FitAssessment = "HIGH" | "MEDIUM" | "LOW";
export type EmploymentType = "FULLTIME" | "PARTTIME" | "CONTRACTOR" | "INTERN";
export type RefreshStatus = "pending" | "running" | "done" | "failed";

export interface JobSummary {
  job_id: string;
  title: string;
  company: string;
  location: string;
  posted_at: string;
  salary_min: number | null;
  salary_max: number | null;
  publisher: string;
  url: string;
  match_score: number;
  fit_assessment: FitAssessment | null;
  applied: boolean;
  description_preview: string;
}

export interface JobListResponse {
  jobs: JobSummary[];
  total: number;
  total_unfiltered: number;
  hidden_by_filters: number;
  last_refreshed_at: string | null;
  next_refresh_allowed_at: string | null;
  candidates_seen: number;
  queries_run: number;
  top_n_cap: number;
}

export interface JobDetailResponse {
  job_id: string;
  title: string;
  company: string;
  location: string;
  posted_at: string;
  salary_min: number | null;
  salary_max: number | null;
  publisher: string;
  url: string;
  description: string;
  match_score: number;
  fit_assessment: FitAssessment | null;
  applied: boolean;
}

export interface RefreshJobResponse {
  refresh_id: string;
  status: "pending";
}

export interface RefreshStatusResponse {
  refresh_id: string;
  status: RefreshStatus;
  started_at: string;
  completed_at: string | null;
  jobs_added: number | null;
  candidates_seen: number | null;
  queries_run: number | null;
  error: string | null;
}

/** Body for POST /jobs/{id}/applied — captured at apply time. */
export interface MarkAppliedRequest {
  letter_version_used?: number | null;
}

/** Per-application audit record on the My Applications page. */
export interface ApplicationSummary {
  job: JobSummary;
  applied_at: string | null;
  resume_filename: string;
  resume_sha256: string;
  letter_version_used: number | null;
  resume_replaced_since: boolean;
}

export interface ApplicationListResponse {
  applications: ApplicationSummary[];
  total: number;
}

/** Body for POST /jobs/manual/fetch — best-effort URL extraction. */
export interface FetchJobUrlRequest {
  url: string;
}

/** Whatever we managed to pull from a URL. Empty fields = couldn't extract. */
export interface FetchJobUrlResponse {
  title: string;
  company: string;
  location: string;
  description: string;
}

/** Body for POST /jobs/manual — create a manually-added job. */
export interface ManualJobRequest {
  title: string;
  company: string;
  description: string;
  location?: string;
  url?: string;
  salary_min?: number | null;
  salary_max?: number | null;
  employment_type?: string;
}

/** Body for POST /jobs/search — the ad-hoc search spec. */
export interface SearchJobsRequest {
  /** 1-3 role terms; each runs its own JSearch query and results merge. */
  what: string[];
  /** 1-3 locations; each (what × where) pair runs its own JSearch query. */
  where: string[];
  salary_min?: number | null;
  employment_types?: EmploymentType[];
  posted_within_days?: number | null;
  /** Override the user's profile default. 1-200, optional. */
  top_n?: number | null;
}

/** Caps match the backend SearchJobsRequest schema. */
export const MAX_WHAT_TERMS = 3;
export const MAX_WHERE_TERMS = 3;

/** Body of the 202 response from POST /jobs/search. */
export interface SearchJobsResponse {
  search_id: string;
  status: "pending";
}

/** Query params for GET /jobs. Multi-value fields are joined with commas. */
export interface JobListFilters {
  filter?: JobFilter;
  type?: string[];
  location?: string[];
  salary_min?: number;
  hide_no_salary?: boolean;
  employment_types?: EmploymentType[];
  posted_within_days?: number;
  [key: string]: string | number | boolean | string[] | undefined;
}

// ---------- Cover letters ----------

export type Verdict = "approved" | "minor_revision" | "rewrite_required";
export type LetterGenerationStatusValue =
  | "pending"
  | "running"
  | "done"
  | "failed";

export interface Strategy {
  fit_assessment: FitAssessment;
  fit_reasoning: string;
  narrative_angle: string;
  primary_project: string;
  secondary_project: string | null;
}

export interface CritiqueScore {
  total: number;
  verdict: Verdict;
  category_scores: Record<string, number>;
  failed_thresholds: string[];
  notes: string;
}

export interface Letter {
  version: number;
  text: string;
  word_count: number;
  strategy: Strategy | null;
  critique: CritiqueScore | null;
  feedback_used: string | null;
  refinement_index: number;
  edited_by_user: boolean;
  created_at: string;
}

export interface LetterVersionList {
  versions: Letter[];
  total: number;
}

export interface GenerateLetterResponse {
  generation_id: string;
  status: "pending";
  estimated_seconds: number;
}

export interface LetterGenerationStatus {
  generation_id: string;
  status: LetterGenerationStatusValue;
  started_at: string;
  completed_at: string | null;
  letter: Letter | null;
  error: string | null;
}

export interface RefineLetterRequest {
  feedback: string;
}

export interface ManualEditRequest {
  text: string;
}

export interface WhyInterestedRequest {
  target_words: number;
}

export interface PolishWhyInterestedRequest {
  text: string;
}

export interface PolishLetterRequest {
  text: string;
}

export interface PolishLetterResponse {
  text: string;
  word_count: number;
}

export interface WhyInterestedResponse {
  text: string;
  word_count: number;
}

// ---------- Saved queries ----------

export interface SavedQuery {
  query_id: string;
  what: string;
  where: string;
  enabled: boolean;
  created_at: string;
}

export interface QueryListResponse {
  queries: SavedQuery[];
  next_refresh_allowed_at: string | null;
}

export interface CreateQueryRequest {
  what: string;
  where: string;
}

export interface UpdateQueryRequest {
  what?: string;
  where?: string;
  enabled?: boolean;
}

// ---------- Profile ----------

export interface ProfileResponse {
  name: string;
  phone: string;
  email: string;
  city: string;
  linkedin_url: string;
  github_url: string;
  portfolio_url: string;
  show_phone_in_header: boolean;
  show_email_in_header: boolean;
  show_city_in_header: boolean;
  show_linkedin_in_header: boolean;
  show_github_in_header: boolean;
  show_portfolio_in_header: boolean;
  top_n_jobs: number;
}

export type UpdateProfileRequest = Partial<ProfileResponse>;

// ---------- Hidden lists ----------

export interface HiddenListsResponse {
  companies: string[];
  title_keywords: string[];
  publishers: string[];
}

export type HiddenListKind = "companies" | "title-keywords" | "publishers";

export interface UpdateHiddenListRequest {
  items: string[];
}

// ---------- Usage ----------

export interface FeatureCount {
  feature: string;
  count: number;
  estimated_cost_usd: number;
}

export interface UsageMonth {
  year_month: string;
  jsearch_calls: number;
  feature_calls: FeatureCount[];
  estimated_anthropic_cost_usd: number;
  estimated_openai_cost_usd: number;
  estimated_total_cost_usd: number;
}

export interface UsageResponse {
  current: UsageMonth;
  history: UsageMonth[];
}

// ---------- Interactive cover letter ----------

export interface CoverLetterAnalysisResponse {
  strong: string[];
  gaps: string[];
  partial: string[];
  excitement_hooks: string[];
  model: string;
}
