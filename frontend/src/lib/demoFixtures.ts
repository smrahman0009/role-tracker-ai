/**
 * Demo-mode fixtures — fictional companies, fictional resume,
 * pre-baked letters and analyses.
 *
 * Everything in this file is **original content** authored for the
 * demo. No real company JDs are reproduced (avoids JSearch ToS,
 * trademark issues, copyright). Company names are plausible-
 * sounding fictional brands; salary bands and tech stacks reflect
 * what real postings in those niches look like circa 2026.
 */

import type {
  ApplicationListResponse,
  CoverLetterAnalysisResponse,
  CoverLetterSummaryResponse,
  GenerateLetterResponse,
  HiddenListsResponse,
  JobDetailResponse,
  JobListResponse,
  JobSummary,
  Letter,
  LetterGenerationStatus,
  LetterVersionList,
  ProfileResponse,
  QueryListResponse,
  ResumeMetadata,
  ResumeUploadResponse,
  SavedQuery,
  UsageMonth,
  UsageResponse,
  WhyInterestedResponse,
} from "@/lib/types";

// ---------------- Mutable in-memory mirror ----------------
//
// Per-tab state so recruiter actions (apply, hide a company, add a
// saved query, replace the resume) appear to "stick" within a
// session. Dies on page reload, which is fine — demo state isn't
// meant to persist.

const appliedJobIds = new Set<string>();
const appliedAt = new Map<string, string>();
const appliedLetterVersion = new Map<string, number | null>();

let hiddenListsState: HiddenListsResponse | null = null;
let queriesState: SavedQuery[] | null = null;
let resumeOverride: ResumeMetadata | null = null;

function getHiddenListsState(): HiddenListsResponse {
  if (hiddenListsState === null) {
    hiddenListsState = {
      companies: [...DEMO_HIDDEN_LISTS.companies],
      title_keywords: [...DEMO_HIDDEN_LISTS.title_keywords],
    };
  }
  return hiddenListsState;
}

function getQueriesState(): SavedQuery[] {
  if (queriesState === null) {
    queriesState = [...DEMO_QUERIES.queries];
  }
  return queriesState;
}

// ---------------- Profile (fictional candidate) ----------------

export const DEMO_PROFILE: ProfileResponse = {
  name: "Mahmud Karim",
  email: "mahmud.karim@example.com",
  phone: "+1 416 555 0142",
  city: "Toronto, ON",
  linkedin_url: "https://linkedin.com/in/mahmud-karim-demo",
  github_url: "https://github.com/mahmud-karim-demo",
  portfolio_url: "https://mahmudkarim.example.com",
  show_phone_in_header: true,
  show_email_in_header: true,
  show_city_in_header: true,
  show_linkedin_in_header: true,
  show_github_in_header: true,
  show_portfolio_in_header: false,
  top_n_jobs: 50,
  is_admin: false,
};

// ---------------- Resume metadata (fictional) ----------------

export const DEMO_RESUME: ResumeMetadata = {
  filename: "mahmud_karim_resume.pdf",
  size_bytes: 187_412,
  uploaded_at: "2026-04-18T14:22:08Z",
  sha256:
    "3f4c1a8e2b5d97c0e4f8a2b1c3d5e7f9a0b2c4d6e8f0a2b4c6d8e0f2a4b6c8d0",
};

// ---------------- Saved queries (fictional) ----------------

export const DEMO_QUERIES: QueryListResponse = {
  queries: [
    {
      query_id: "q1",
      what: "machine learning engineer",
      where: "canada",
      enabled: true,
      created_at: "2026-04-20T09:14:00Z",
    },
    {
      query_id: "q2",
      what: "ML platform engineer",
      where: "remote",
      enabled: true,
      created_at: "2026-04-22T11:30:00Z",
    },
    {
      query_id: "q3",
      what: "applied scientist NLP",
      where: "toronto",
      enabled: false,
      created_at: "2026-04-25T15:42:00Z",
    },
  ],
  next_refresh_allowed_at: null,
};

// ---------------- Hidden lists ----------------

export const DEMO_HIDDEN_LISTS: HiddenListsResponse = {
  companies: ["Stealth Mode Co", "Acme Outsourcing"],
  title_keywords: ["intern", "junior", "phd required"],
};

// Global hidden publishers (admin-managed). Demo users are not admin
// so the Settings card is hidden, but the canned list is still
// returned by GET /global/hidden-publishers for completeness.
export const DEMO_GLOBAL_HIDDEN_PUBLISHERS = {
  publishers: ["ZipRecruiter", "Indeed Aggregator"],
  updated_at: "2026-05-01T12:00:00Z",
  updated_by: "admin",
};

// ---------------- Jobs (7 fictional postings) ----------------
//
// Each posting is original prose, ~150-250 words, written to feel
// real without being any one company's. Variety in industry, level,
// salary band, and "fit" to the demo resume — so the user can play
// with the agent's strategy choices on different scenarios.

const J_BLUEOCEAN: JobDetailResponse = {
  job_id: "demo-blueocean-mle",
  title: "Senior Machine Learning Engineer",
  company: "BlueOcean Data",
  location: "Toronto, ON (Hybrid, 2 days/week in office)",
  posted_at: "2026-05-04",
  salary_min: 160_000,
  salary_max: 200_000,
  publisher: "BlueOcean Careers",
  url: "https://example.com/blueocean/senior-mle",
  description: `BlueOcean Data is hiring a Senior Machine Learning Engineer to join the Risk team. The team owns fraud-detection ML systems that process roughly 40 million transactions a day for our SMB customers.

You'll work on the full lifecycle: model development, feature pipelines, deployment, monitoring, and incident response. The current stack is Python + PyTorch for modelling, Spark for batch features, and a custom online inference platform built on AWS.

Requirements:
- 4+ years shipping production ML systems (not just notebooks).
- Strong Python, comfortable in PyTorch or another deep-learning framework.
- Experience with distributed processing (Spark, Beam, or similar).
- Track record of designing features that survive contact with production data drift.

Nice to have:
- Background in fraud, anti-abuse, or other adversarial-ML domains.
- Experience with online inference latency requirements (sub-100ms).
- Comfortable on-call for production model incidents.

Compensation: CAD 160-200k base + equity. Hybrid Toronto (Bay/Adelaide office), two days a week minimum. Remote candidates considered for exceptional fits within Canada.`,
  match_score: 0.84,
  fit_assessment: "HIGH",
  applied: false,
};

const J_HELIO: JobDetailResponse = {
  job_id: "demo-helio-staff-ds",
  title: "Staff Data Scientist, Recommender Systems",
  company: "Helio Labs",
  location: "Remote (North America)",
  posted_at: "2026-05-02",
  salary_min: 200_000,
  salary_max: 250_000,
  publisher: "Helio Labs Jobs",
  url: "https://example.com/helio/staff-ds",
  description: `Helio Labs builds discovery experiences for independent media — currently 8 million MAU across our podcast and newsletter products. We're hiring a Staff Data Scientist to lead the recommender systems track.

The role is part senior IC, part technical lead. You'll own the recommendation roadmap end-to-end: offline experimentation, online A/B testing infrastructure, and production model deployment. Expect to mentor 2-3 mid-level data scientists and partner closely with the platform engineering team.

What you'll do:
- Define and ship the next generation of our content recommender (currently a two-tower neural model with content embeddings + behavioural signals).
- Build and own the experimentation platform — we run roughly 30 concurrent A/B tests.
- Set the technical bar for the DS team's modelling and analysis work.

What we want:
- 7+ years in applied ML or data science, with at least 2 years on recommendations specifically.
- Deep experience with neural recommender architectures (two-tower, transformers, sequence models).
- Strong opinions on causal inference and experimentation methodology.

Comp: $200-250k USD base + meaningful equity. Fully remote within North America.`,
  match_score: 0.71,
  fit_assessment: "MEDIUM",
  applied: false,
};

const J_RIDGE: JobDetailResponse = {
  job_id: "demo-ridge-mlplatform",
  title: "ML Platform Engineer",
  company: "Ridge Analytics",
  location: "Berlin, Germany (Hybrid)",
  posted_at: "2026-05-05",
  salary_min: 110_000,
  salary_max: 140_000,
  publisher: "Ridge Engineering",
  url: "https://example.com/ridge/ml-platform-engineer",
  description: `Ridge Analytics provides risk-scoring infrastructure to mid-market European banks. Our ML platform team builds the internal tools 30+ data scientists use every day to ship models into production.

We're looking for an ML Platform Engineer to drive the next year of platform investment: better notebook-to-production paths, faster CI for ML PRs, and observability that catches model drift before customers do.

You'll be working on:
- Our internal model-serving platform (Python/FastAPI, gRPC, deployed on Kubernetes).
- Feature store rollout (currently in pilot, used by 3 of our 12 model teams).
- CI/CD for ML — bringing our DS workflow up to par with our backend team's standards.

Looking for:
- 3+ years building developer tools or platform infrastructure.
- Strong Python; comfortable with Go or Rust for performance-critical components.
- Hands-on with Kubernetes, container orchestration, and AWS or GCP at scale.
- ML literacy — you don't need to train models, but you need to understand why an MLE's life is hard.

Compensation: €110-140k + equity. Berlin office, three days a week.`,
  match_score: 0.62,
  fit_assessment: "MEDIUM",
  applied: false,
};

const J_QUANTA: JobDetailResponse = {
  job_id: "demo-quanta-aiml",
  title: "AI/ML Engineer, Clinical NLP",
  company: "Quanta Health",
  location: "Boston, MA (Hybrid)",
  posted_at: "2026-04-30",
  salary_min: 180_000,
  salary_max: 220_000,
  publisher: "Quanta Health Careers",
  url: "https://example.com/quanta/aiml-clinical-nlp",
  description: `Quanta Health builds clinical-decision-support tools used by 600+ hospitals across the US. Our NLP team turns unstructured clinical notes into structured signals that downstream care teams can act on.

We're hiring an AI/ML Engineer to focus on the LLM side of our pipeline: building, evaluating, and deploying domain-tuned language models for medical-record extraction and summarisation.

You'll own:
- LLM evaluation pipelines for clinical accuracy (we work closely with physicians on rubric design).
- Fine-tuning and adaptation work — both prompt-engineering at scale and parameter-efficient methods.
- Production deployment of LLM-based features behind strict latency and HIPAA constraints.

Required:
- 3+ years working with LLMs in production (not just prompting demos).
- Solid grounding in NLP fundamentals — tokenisation, retrieval, evaluation methodology.
- Either prior health-tech experience OR willingness to ramp on the regulatory environment quickly.

Bonus:
- Published or shipped work on LLM evaluation, RAG, or domain adaptation.
- Experience working with PHI under HIPAA controls.

Comp: $180-220k base + equity + benefits. Hybrid in Cambridge, MA (3 days in-office).`,
  match_score: 0.79,
  fit_assessment: "HIGH",
  applied: false,
};

const J_VERTEX: JobDetailResponse = {
  job_id: "demo-vertex-cv",
  title: "Computer Vision Engineer",
  company: "Vertex Robotics",
  location: "San Francisco, CA",
  posted_at: "2026-04-29",
  salary_min: 200_000,
  salary_max: 260_000,
  publisher: "Vertex Robotics Hiring",
  url: "https://example.com/vertex/computer-vision-engineer",
  description: `Vertex Robotics is building autonomous warehouse robots — currently in pilot deployments at 4 fulfilment centres, scaling to 40+ over the next 18 months. Our perception team is hiring a Computer Vision Engineer to work on real-time object detection and scene understanding for our next-gen platform.

What the role looks like:
- Build production CV models that run on-board our robots (jetson-class hardware, real-time constraints).
- Own the data pipeline from raw camera feeds → labelling → training → deployment.
- Partner with the planning and controls teams to make sure perception output is *useful* to downstream decision-makers, not just accurate.

What we need:
- 3+ years shipping CV in production. Bonus if it ran on-edge.
- Strong PyTorch (or equivalent), comfortable with quantisation and inference optimisation.
- Practical experience with the unglamorous parts: data labelling pipelines, dataset versioning, model lifecycle.

Less important:
- Specific industry. We hire from autonomy, retail, surveillance, AR/VR — perception is perception.
- Advanced degree. We've hired strong engineers with BS-level academic backgrounds.

Comp: $200-260k base + equity. Onsite SF (Mission Bay), 4 days a week minimum.`,
  match_score: 0.41,
  fit_assessment: "LOW",
  applied: false,
};

const J_TESSERA: JobDetailResponse = {
  job_id: "demo-tessera-founding",
  title: "Founding ML Engineer",
  company: "Tessera AI",
  location: "Remote (Americas + EU)",
  posted_at: "2026-05-06",
  salary_min: 130_000,
  salary_max: 180_000,
  publisher: "Tessera AI",
  url: "https://example.com/tessera/founding-ml-engineer",
  description: `Tessera AI is a 6-person seed-stage startup building developer tools for ML evaluation. We just closed a $4M seed led by a top-tier US fund and have 8 design partners using the alpha.

We're hiring a founding ML engineer (employee #5 on the engineering side). You'll work directly with the founders on product direction, ship customer-facing features end-to-end, and have meaningful equity (0.5-1.5%).

The work spans:
- Product engineering — building the actual UI + APIs developers integrate into their pipelines.
- Applied ML — designing the evaluation methodologies our customers rely on.
- Customer engineering — sitting in calls with our design partners, watching their workflows, shipping the right thing.

We want someone who:
- Has shipped production software (not just experiments). 4+ years.
- Is comfortable with both ML modelling and full-stack engineering. Polyglot energy.
- Wants the founding-engineer experience: chaos, ownership, equity, real risk.

Compensation: $130-180k base (deliberately below market — you're trading cash for equity), 0.5-1.5% equity, fully remote. Travel ~once a quarter for offsites.`,
  match_score: 0.68,
  fit_assessment: "MEDIUM",
  applied: false,
};

const J_NORTHWIND: JobDetailResponse = {
  job_id: "demo-northwind-sds",
  title: "Senior Data Scientist, Operations",
  company: "Northwind Logistics",
  location: "Toronto, ON",
  posted_at: "2026-04-26",
  salary_min: 140_000,
  salary_max: 170_000,
  publisher: "Northwind Careers",
  url: "https://example.com/northwind/senior-data-scientist",
  description: `Northwind Logistics moves roughly 80,000 parcels a day across Canada. We're hiring a Senior Data Scientist to join the Network Operations team — the group that makes sure the right truck has the right packages at the right time.

You'll work on routing, forecasting, and capacity planning. Specific projects we'd want you on this year:
- Re-baselining our daily volume forecast after a 30% YoY growth shift.
- Building the optimiser for our new same-day pickup product.
- Improving driver-shift planning under uncertainty.

Looking for:
- 5+ years applied data science, with operations research / optimisation experience preferred.
- Strong Python; SQL fluency; comfortable with cloud data warehouses.
- Track record of translating messy operational problems into models that ship and stick.

Bonus:
- Time-series forecasting experience (especially under regime shifts).
- Background in OR (linear programming, MIP, vehicle routing).

Compensation: CAD 140-170k base. Toronto, with most of the team in-office 3 days a week. Health, dental, pension match.`,
  match_score: 0.55,
  fit_assessment: "MEDIUM",
  applied: false,
};

const ALL_JOBS: JobDetailResponse[] = [
  J_BLUEOCEAN,
  J_HELIO,
  J_RIDGE,
  J_QUANTA,
  J_VERTEX,
  J_TESSERA,
  J_NORTHWIND,
];

// ---------------- Manually-added jobs (3 fictional URL-paste entries) ----------------
//
// The "Added jobs" page shows postings the user found themselves and
// pasted in by URL — independent of the daily ranked snapshot. These
// three are styled to look like things a candidate might paste from
// a friend's referral or a careers page they bookmarked.

const M_HELIX: JobDetailResponse = {
  job_id: "demo-manual-helix-mle",
  title: "ML Engineer — Generative Models",
  company: "Helix Visual",
  location: "Remote (Worldwide)",
  posted_at: "2026-05-03",
  salary_min: 150_000,
  salary_max: 200_000,
  publisher: "Helix Visual Careers",
  url: "https://example.com/helix/ml-engineer-generative",
  description: `Helix Visual is building generative-image tools for indie game studios. We've shipped to about 200 studios in beta and are scaling to public launch this year. We're hiring an ML Engineer to focus on inference performance and customer-facing model behaviour.

You'll work on:
- Latency optimisation for our diffusion-based pipeline (currently 4-8 seconds per generation; target sub-2s).
- Prompt-handling and safety filters that work for game-asset generation specifically.
- Deployment infrastructure for our inference fleet (GPU spot instances, queue management, autoscaling).

Looking for someone with:
- 3+ years shipping ML in production. Inference-time performance work is a strong plus.
- Deep PyTorch comfort. Diffusion-model architecture knowledge helpful.
- Practical experience with GPU serving (Triton, vLLM, or equivalent).

Comp: $150-200k base + early-stage equity. Fully remote, async-first culture, quarterly team meetups.`,
  match_score: 0.66,
  fit_assessment: "MEDIUM",
  applied: false,
};

const M_PARALLAX: JobDetailResponse = {
  job_id: "demo-manual-parallax-ds",
  title: "Senior Data Scientist, Growth",
  company: "Parallax",
  location: "New York, NY (Hybrid)",
  posted_at: "2026-05-01",
  salary_min: 175_000,
  salary_max: 220_000,
  publisher: "Parallax Careers",
  url: "https://example.com/parallax/senior-ds-growth",
  description: `Parallax is a B2B SaaS company building project-management software for creative agencies. We have 1,200 paying customers, $20M ARR, and we're hiring our second senior data scientist on the Growth team.

The role is a mix of analytics and applied ML:
- Funnel analysis: figure out where users drop off in onboarding and what to do about it.
- Pricing experiments: design and run pricing-page A/B tests with the GTM team.
- Lifetime-value modelling: build a churn-and-LTV model that the sales team can act on.

What we're looking for:
- 5+ years applied data science, ideally in B2B SaaS.
- Strong Python + SQL. Comfortable with our data warehouse (Snowflake) and our experimentation platform (Statsig).
- Ability to communicate with non-technical stakeholders. Most of your influence comes from how you frame results, not from the model itself.

Comp: $175-220k base + equity. Hybrid in NYC (3 days a week in office, on-site Tuesday + Thursday + one floating).`,
  match_score: 0.52,
  fit_assessment: "MEDIUM",
  applied: false,
};

const M_TIDEWATER: JobDetailResponse = {
  job_id: "demo-manual-tidewater-mlops",
  title: "MLOps Engineer",
  company: "Tidewater Climate",
  location: "Vancouver, BC",
  posted_at: "2026-04-28",
  salary_min: 130_000,
  salary_max: 165_000,
  publisher: "Tidewater Climate",
  url: "https://example.com/tidewater/mlops-engineer",
  description: `Tidewater Climate builds satellite-imagery analysis tools for shipping companies tracking ocean and weather conditions. Series-B stage, 80 employees, mission-driven (we offset our compute use plus 1.5×).

We're hiring an MLOps Engineer to take over a stack that's grown organically from prototype scripts to production. Your first six months:
- Migrate the model-training pipeline from ad-hoc scripts to a managed orchestrator (likely Prefect or Argo).
- Build the model registry + CI workflow our DS team needs to deploy without engineering bottleneck.
- Replace our current "deploy by SSH" inference layer with a proper container-based platform.

Required:
- 3+ years ops or DevOps with significant ML exposure.
- Strong Python, comfortable with one of: Argo, Prefect, Kubeflow, Airflow.
- Cloud experience — we're on AWS.

Nice to have:
- Geospatial / satellite-imagery domain.
- Climate or ocean-modelling background.

CAD 130-165k + equity + stock-based bonuses. Vancouver office (Mount Pleasant), 3 days/week. Strong work-life balance — we don't believe in evening incidents unless something's literally on fire.`,
  match_score: 0.61,
  fit_assessment: "MEDIUM",
  applied: false,
};

const ALL_MANUAL_JOBS: JobDetailResponse[] = [
  M_HELIX,
  M_PARALLAX,
  M_TIDEWATER,
];

// ---------------- API response shapes built from the jobs ----------------

function toSummary(job: JobDetailResponse): JobSummary {
  return {
    job_id: job.job_id,
    title: job.title,
    company: job.company,
    location: job.location,
    posted_at: job.posted_at,
    salary_min: job.salary_min,
    salary_max: job.salary_max,
    publisher: job.publisher,
    url: job.url,
    match_score: job.match_score,
    fit_assessment: job.fit_assessment,
    applied: appliedJobIds.has(job.job_id) || job.applied,
    description_preview: job.description.slice(0, 220) + "…",
  };
}

function withAppliedFlag(job: JobDetailResponse): JobDetailResponse {
  return appliedJobIds.has(job.job_id)
    ? { ...job, applied: true }
    : job;
}

export function demoJobList(): JobListResponse {
  return {
    jobs: ALL_JOBS.map(toSummary),
    total: ALL_JOBS.length,
    total_unfiltered: ALL_JOBS.length,
    hidden_by_filters: 0,
    last_refreshed_at: "2026-05-08T08:14:32Z",
    next_refresh_allowed_at: null,
    candidates_seen: 247,
    queries_run: 3,
    top_n_cap: 50,
  };
}

export function demoJobDetail(jobId: string): JobDetailResponse | null {
  const found =
    ALL_JOBS.find((j) => j.job_id === jobId) ??
    ALL_MANUAL_JOBS.find((j) => j.job_id === jobId) ??
    userAddedManualJobs.find((j) => j.job_id === jobId) ??
    null;
  return found ? withAppliedFlag(found) : null;
}

/** Manually-added jobs added by the recruiter at runtime via the
 *  paste-URL flow. Persisted in-memory so they show up on the list
 *  page. */
const userAddedManualJobs: JobDetailResponse[] = [];

export function demoDeleteManualJob(jobId: string): void {
  const idx = userAddedManualJobs.findIndex((j) => j.job_id === jobId);
  if (idx !== -1) userAddedManualJobs.splice(idx, 1);
}

export function demoAppendManualJob(job: JobDetailResponse): void {
  // Avoid dupes if the same job_id is saved twice.
  if (
    userAddedManualJobs.some((j) => j.job_id === job.job_id) ||
    ALL_MANUAL_JOBS.some((j) => j.job_id === job.job_id)
  ) {
    return;
  }
  userAddedManualJobs.unshift(job);
}

/** List of manually-added jobs (the /added-jobs page).
 *  Returned as a JobListResponse like the main jobs list. */
export function demoManualJobsList(): JobListResponse {
  const jobs = [...userAddedManualJobs, ...ALL_MANUAL_JOBS];
  return {
    jobs: jobs.map(toSummary),
    total: jobs.length,
    total_unfiltered: jobs.length,
    hidden_by_filters: 0,
    last_refreshed_at: null,
    next_refresh_allowed_at: null,
    candidates_seen: 0,
    queries_run: 0,
    top_n_cap: 0,
  };
}

/** Returned by POST /jobs/manual/fetch when the user pastes a URL.
 *  In demo mode we return one of the canned manual jobs so the
 *  full "paste URL → preview → save" interaction works. */
export function demoFetchedJob(): JobDetailResponse {
  // Pick one of the manual entries; rotating so a recruiter who
  // pastes multiple URLs sees variety.
  const idx = Math.floor(Math.random() * ALL_MANUAL_JOBS.length);
  return ALL_MANUAL_JOBS[idx];
}

// ---------------- JD summary (one canned per job) ----------------

const SUMMARIES: Record<string, CoverLetterSummaryResponse> = {
  "demo-blueocean-mle": {
    role: "Senior IC role on the Risk team building production fraud-detection ML systems on a custom online-inference platform. Sub-100ms latency expectations.",
    requirements: "4+ years shipping production ML, strong Python and PyTorch, distributed processing (Spark/Beam), feature engineering for production drift.",
    context: "Hybrid in Toronto (2 days in office), $160-200k CAD plus equity. On-call rotation for production model incidents.",
    model: "claude-sonnet-4-6",
  },
  "demo-helio-staff-ds": {
    role: "Staff IC + technical lead role on the recommendations track for an 8M MAU media-discovery product. Mentors 2-3 mid-level DSs.",
    requirements: "7+ years applied ML/DS, 2+ on recommendations specifically, deep experience with neural recommenders (two-tower, transformers), strong causal-inference and experimentation chops.",
    context: "Fully remote within North America, $200-250k USD plus meaningful equity. Owns the experimentation platform (~30 concurrent A/B tests).",
    model: "claude-sonnet-4-6",
  },
  "demo-ridge-mlplatform": {
    role: "Platform-engineering role serving 30+ data scientists at a European risk-scoring company. Drives the model-serving platform, feature store rollout, and ML CI/CD.",
    requirements: "3+ years platform / developer-tools work, strong Python plus Go or Rust, hands-on Kubernetes and AWS or GCP, ML literacy without needing to train models.",
    context: "Berlin hybrid (3 days/week), €110-140k plus equity. Mid-market European banking customers.",
    model: "claude-sonnet-4-6",
  },
  "demo-quanta-aiml": {
    role: "LLM-focused AI/ML role at a clinical-decision-support company serving 600+ US hospitals. Owns LLM eval, fine-tuning/adaptation, and HIPAA-constrained production deploys.",
    requirements: "3+ years LLMs in production, NLP fundamentals (tokenisation, retrieval, evaluation methodology), prior health-tech experience or fast ramp on regulatory work.",
    context: "Hybrid in Cambridge MA (3 days/week), $180-220k. Strong rubric-design partnership with physicians.",
    model: "claude-sonnet-4-6",
  },
  "demo-vertex-cv": {
    role: "Computer-vision IC role on the perception team of an autonomous-warehouse-robotics startup. On-edge inference (jetson-class hardware), real-time constraints.",
    requirements: "3+ years CV in production (bonus if on-edge), strong PyTorch with quantisation experience, hands-on with the full data-pipeline lifecycle.",
    context: "Onsite SF (Mission Bay) 4 days/week, $200-260k plus equity. Pilot at 4 fulfilment centres scaling to 40+ over 18 months.",
    model: "claude-sonnet-4-6",
  },
  "demo-tessera-founding": {
    role: "Founding ML engineer at a 6-person seed-stage developer-tools startup ($4M seed). Mix of product, applied ML, and customer engineering work.",
    requirements: "4+ years shipping production software, comfortable across ML modelling and full-stack engineering, founder-mode appetite for chaos plus ownership.",
    context: "Fully remote, $130-180k base (below market) plus 0.5-1.5% equity. ~quarterly travel for offsites.",
    model: "claude-sonnet-4-6",
  },
  "demo-northwind-sds": {
    role: "Senior data-science role on Network Operations at a Canadian logistics company moving 80k parcels/day. Routing, forecasting, capacity planning.",
    requirements: "5+ years applied DS with operations-research or optimisation flavour, strong Python and SQL, track record of shipping models that survive operational reality.",
    context: "Toronto in-office 3 days/week, CAD 140-170k. Active projects: volume re-baseline post 30% YoY growth, same-day pickup optimiser, driver-shift planning.",
    model: "claude-sonnet-4-6",
  },
};

export function demoSummary(jobId: string): CoverLetterSummaryResponse | null {
  return SUMMARIES[jobId] ?? null;
}

// ---------------- Match analysis (one canned per job) ----------------

const ANALYSES: Record<string, CoverLetterAnalysisResponse> = {
  "demo-blueocean-mle": {
    strong: [
      "Production ML experience matches their 'past prototype phase' requirement — Mahmud shipped two large fraud-adjacent models at SafeStream Financial",
      "Strong PyTorch background, including the on-call cycle for the FraudGuard project",
      "Spark experience from the SafeStream batch features pipeline",
    ],
    gaps: [
      "JD mentions sub-100ms online inference; Mahmud's resume is heavier on batch + near-real-time, not strict sub-100ms",
    ],
    partial: [
      "Online inference platform work — Mahmud built one on Kubernetes, BlueOcean's is custom-built",
    ],
    excitement_hooks: [
      "Risk team specifically builds fraud-detection ML — direct domain match",
      "40M transactions/day is an order of magnitude bigger than Mahmud's last system",
      "Hybrid Toronto matches Mahmud's stated city",
    ],
    model: "claude-sonnet-4-6",
  },
  "demo-helio-staff-ds": {
    strong: [
      "Two-tower recommender experience from Mahmud's Lumen Media project (4M MAU)",
      "A/B testing platform ownership at SafeStream — built the experimentation framework currently used by 9 ML teams",
    ],
    gaps: [
      "JD asks for 7+ years; Mahmud's resume shows 5",
      "Causal inference is mentioned briefly but not as a core strength",
    ],
    partial: [
      "Mentoring experience — informal lead of 1 junior, not 2-3 mid-levels",
    ],
    excitement_hooks: [
      "Independent-media discovery problem is genuinely interesting (mentioned in cover letters Mahmud has written)",
      "Staff IC + tech lead is the next career step for Mahmud",
      "Fully remote North America matches Mahmud's stated remote preference",
    ],
    model: "claude-sonnet-4-6",
  },
  "demo-ridge-mlplatform": {
    strong: [
      "Platform-team experience at SafeStream — Mahmud owned the feature-store rollout to 6 of 14 ML teams",
      "Strong Kubernetes and AWS",
    ],
    gaps: [
      "JD asks for Go or Rust; Mahmud's resume shows Python and a little C++ only",
      "European banking domain is unfamiliar territory",
    ],
    partial: [
      "ML CI/CD work — Mahmud built a notebook-to-prod pipeline at Lumen, less polished than what Ridge needs",
    ],
    excitement_hooks: [
      "Solving the 'notebook-to-production' problem at scale is what Mahmud did at Lumen and wants to keep doing",
      "Smaller team (12 model teams) sized for high impact per platform engineer",
    ],
    model: "claude-sonnet-4-6",
  },
  "demo-quanta-aiml": {
    strong: [
      "LLM evaluation work from the FraudGuard explanation project — Mahmud designed the rubric for hallucination + grounding scoring",
      "Production LLM deploys including a HIPAA-adjacent project at Lumen Media",
      "NLP fundamentals from undergrad and the medical-record extraction prototype",
    ],
    gaps: [
      "Direct health-tech experience is limited — a single research project, not production",
    ],
    partial: [
      "Fine-tuning experience — instruction-tuning Llama-2 for FraudGuard, not parameter-efficient methods",
    ],
    excitement_hooks: [
      "LLM eval at clinical accuracy levels is exactly the work Mahmud wants to do next",
      "Working with physicians on rubric design is unusually concrete for an ML role",
      "Cambridge MA hybrid is workable for Mahmud (open to relocation per profile)",
    ],
    model: "claude-sonnet-4-6",
  },
  "demo-vertex-cv": {
    strong: [
      "Strong PyTorch from the Lumen recommender work",
    ],
    gaps: [
      "No computer-vision experience on the resume — the closest match is image-embedding work for a content-similarity feature",
      "No edge-deployment or quantisation experience",
      "No autonomy / robotics domain background",
    ],
    partial: [
      "Production-ML mindset translates across domains, but Vertex's stack is otherwise unfamiliar",
    ],
    excitement_hooks: [
      "Real-time perception problem is technically meaty",
      "On-edge inference is an unusual constraint Mahmud hasn't worked under",
    ],
    model: "claude-sonnet-4-6",
  },
  "demo-tessera-founding": {
    strong: [
      "Full-stack engineering experience — Mahmud shipped product features end-to-end at Lumen (UI through serving)",
      "ML evaluation work directly — designed and maintained the FraudGuard rubric scorer",
      "Polyglot mindset matches founding-engineer expectation",
    ],
    gaps: [
      "Customer-engineering specifically (sitting in design-partner calls) is light on the resume",
    ],
    partial: [
      "Startup experience — Mahmud has worked at scale-ups (SafeStream, Lumen) but not 6-person seed",
    ],
    excitement_hooks: [
      "Building the eval product Mahmud wishes existed at SafeStream is direct dogfood",
      "Founding-engineer ownership and equity match Mahmud's career-stage instincts",
      "0.5-1.5% equity at a $4M seed is meaningful upside",
    ],
    model: "claude-sonnet-4-6",
  },
  "demo-northwind-sds": {
    strong: [
      "Forecasting experience — Mahmud built the demand-volume forecaster for SafeStream's reconciliation team",
      "Strong Python + SQL",
    ],
    gaps: [
      "Operations research / optimisation specifically — Mahmud has touched LP via convex-optimisation coursework, not shipped MIP solutions",
      "Vehicle-routing-style problems are not on the resume",
    ],
    partial: [
      "Time-series forecasting — solid fundamentals, but regime-shift specifically (their 30% YoY growth scenario) is harder",
    ],
    excitement_hooks: [
      "Toronto match for location preference",
      "Concrete problems (volume forecast re-baseline, same-day pickup optimiser) translate cleanly into resume bullets later",
      "Operations role gives variety vs another adjacent ML role",
    ],
    model: "claude-sonnet-4-6",
  },
};

export function demoAnalysis(jobId: string): CoverLetterAnalysisResponse | null {
  return ANALYSES[jobId] ?? null;
}

// ---------------- Pre-baked letter (BlueOcean v1) ----------------

const BLUEOCEAN_LETTER_V1_TEXT = `**Mahmud Karim**
+1 416 555 0142 | mahmud.karim@example.com | Toronto, ON
https://linkedin.com/in/mahmud-karim-demo | https://github.com/mahmud-karim-demo

Dear BlueOcean Data Team,

I'm writing because the FraudGuard project at SafeStream Financial taught me lessons that map directly to what your Risk team is building. Production fraud-detection ML at the volume you operate at is a different problem from offline modelling, and I've spent the last two years on the production side of that gap.

At SafeStream, I led the rebuild of FraudGuard's online inference layer after we hit drift-related precision regressions in late 2024. We moved from a daily batch pipeline to a hybrid online + nightly batch system serving roughly 12 million transactions a day, with a strict 80ms p95 latency budget. The work spanned model architecture (a two-tower neural model with behavioural and merchant-side features), serving infrastructure (PyTorch on a custom Kubernetes platform), and the feature pipeline rebuild on Spark. The system has been in production for 14 months; precision-at-fixed-recall improved 11% relative to the legacy baseline.

What I'd bring to BlueOcean specifically is the on-call discipline. The hardest part of the FraudGuard work wasn't building the system — it was the months after launch, when the team rotated through 24x7 on-call and we surfaced (and fixed) the long tail of failure modes the offline tests missed. Production ML at this scale is a sustained operational effort, and I'd want to be on that rotation from day one.

Best,
Mahmud Karim`;

const BLUEOCEAN_LETTER_V1: Letter = {
  version: 1,
  text: BLUEOCEAN_LETTER_V1_TEXT,
  word_count: 248,
  strategy: {
    fit_assessment: "HIGH",
    fit_reasoning: "Direct domain match (fraud-detection ML) plus production-scale experience with similar latency constraints.",
    narrative_angle: "Production fraud-detection ML at scale is a different problem from offline modelling — and I've spent two years on that side.",
    primary_project: "FraudGuard online inference rebuild at SafeStream Financial",
    secondary_project: null,
  },
  critique: {
    total: 96,
    verdict: "approved",
    category_scores: {
      hallucination: 25,
      tailoring: 22,
      voice: 17,
      banned_phrases: 10,
      structure: 12,
      gap_handling: 10,
    },
    failed_thresholds: [],
    notes: "Clean draft — strong concrete metric, on-call angle is distinctive.",
  },
  feedback_used: null,
  refinement_index: 0,
  edited_by_user: false,
  created_at: "2026-05-08T10:14:23Z",
};

const LETTERS: Record<string, Letter[]> = {
  "demo-blueocean-mle": [BLUEOCEAN_LETTER_V1],
};

export function demoLetterVersions(jobId: string): LetterVersionList {
  const versions = LETTERS[jobId] ?? [];
  return { versions: [...versions].reverse(), total: versions.length };
}

export function demoLetter(
  jobId: string,
  version: number,
): Letter | null {
  return LETTERS[jobId]?.find((l) => l.version === version) ?? null;
}

/** Append a fake "saved" letter (used when the user clicks Generate
 *  in demo mode and we need to update the version list in-memory). */
export function demoAppendLetter(jobId: string, letter: Letter): void {
  if (!LETTERS[jobId]) LETTERS[jobId] = [];
  LETTERS[jobId].push(letter);
}

/** What the agent's "fake generation" returns when the user clicks
 *  Generate. Slightly different per-job so the demo doesn't show
 *  the same letter for everything. */
export function demoFakeLetter(jobId: string): Letter {
  const job = demoJobDetail(jobId);
  const company = job?.company ?? "the company";
  const title = job?.title ?? "the role";
  const text = `**Mahmud Karim**
+1 416 555 0142 | mahmud.karim@example.com | Toronto, ON
https://linkedin.com/in/mahmud-karim-demo | https://github.com/mahmud-karim-demo

Dear ${company} Team,

I'm writing because the work I did on the FraudGuard project at SafeStream Financial maps directly to the ${title} role you're hiring for. Specifically, the production-ML experience your JD emphasises is the work I've spent the last two years doing.

At SafeStream, I led a rebuild of an online inference system serving roughly 12 million transactions a day, with strict latency budgets and on-call ownership. The work spanned model architecture, serving infrastructure on Kubernetes, and a feature-pipeline rebuild on Spark. The system has been in production for 14 months and improved precision-at-fixed-recall 11% over the previous baseline.

The piece that I'd carry into ${company} specifically is the discipline that comes from owning the production lifecycle — the failure modes you only see months after launch, the cost-vs-recall trade-offs that don't show up in offline metrics, the patience to keep iterating after the launch announcement is over.

Best,
Mahmud Karim`;
  const newVersion =
    (LETTERS[jobId]?.length ?? 0) + 1;
  return {
    version: newVersion,
    text,
    word_count: text.split(/\s+/).filter(Boolean).length,
    strategy: {
      fit_assessment: "HIGH",
      fit_reasoning:
        "Production-ML experience and similar-scale system ownership map cleanly.",
      narrative_angle:
        "Production-ML lifecycle ownership is what I've been doing for two years.",
      primary_project: "FraudGuard online inference rebuild at SafeStream",
      secondary_project: null,
    },
    critique: {
      total: 92,
      verdict: "approved",
      category_scores: {
        hallucination: 24,
        tailoring: 20,
        voice: 17,
        banned_phrases: 10,
        structure: 12,
        gap_handling: 9,
      },
      failed_thresholds: [],
      notes: "Demo-mode sample. In live mode this would be tailored.",
    },
    feedback_used: null,
    refinement_index: 0,
    edited_by_user: false,
    created_at: new Date().toISOString(),
  };
}

// ---------------- Other simple endpoints ----------------

export const DEMO_USAGE: UsageResponse = {
  current: makeMonth("2026-05", 14, {
    cover_letter_generate: 3,
    cover_letter_summary: 5,
    cover_letter_analysis: 4,
    cover_letter_polish: 2,
    embedding: 18,
    why_interested_polish: 1,
  }),
  history: [
    makeMonth("2026-04", 87, {
      cover_letter_generate: 12,
      cover_letter_summary: 18,
      cover_letter_analysis: 15,
      cover_letter_polish: 7,
      embedding: 64,
    }),
    makeMonth("2026-03", 41, {
      cover_letter_generate: 6,
      cover_letter_summary: 9,
      cover_letter_analysis: 7,
      cover_letter_polish: 3,
      embedding: 32,
    }),
  ],
};

function makeMonth(
  ym: string,
  jsearch: number,
  features: Record<string, number>,
): UsageMonth {
  const PER_CALL: Record<string, number> = {
    cover_letter_generate: 0.05,
    cover_letter_refine: 0.025,
    cover_letter_polish: 0.005,
    cover_letter_summary: 0.020,
    cover_letter_analysis: 0.020,
    why_interested_polish: 0.005,
    embedding: 0.0005,
  };
  const featureCalls = Object.entries(features).map(([feature, count]) => ({
    feature,
    count,
    estimated_cost_usd: count * (PER_CALL[feature] ?? 0),
  }));
  const isAnthropic = (f: string) =>
    f.startsWith("cover_letter") || f.startsWith("why_");
  return {
    year_month: ym,
    jsearch_calls: jsearch,
    feature_calls: featureCalls,
    estimated_anthropic_cost_usd: featureCalls
      .filter((f) => isAnthropic(f.feature))
      .reduce((acc, f) => acc + f.estimated_cost_usd, 0),
    estimated_openai_cost_usd: featureCalls
      .filter((f) => f.feature === "embedding")
      .reduce((acc, f) => acc + f.estimated_cost_usd, 0),
    estimated_total_cost_usd: 0, // recomputed below
  };
}

// Patch the totals — TypeScript doesn't let us self-reference cleanly above.
for (const m of [DEMO_USAGE.current, ...DEMO_USAGE.history]) {
  m.estimated_total_cost_usd =
    m.estimated_anthropic_cost_usd + m.estimated_openai_cost_usd;
}

// Seed: BlueOcean is pre-applied so the Applications page isn't
// empty on first visit.
appliedJobIds.add(J_BLUEOCEAN.job_id);
appliedAt.set(J_BLUEOCEAN.job_id, "2026-05-06T16:42:00Z");
appliedLetterVersion.set(J_BLUEOCEAN.job_id, 1);

export function demoApplications(): ApplicationListResponse {
  const all = [...ALL_JOBS, ...ALL_MANUAL_JOBS];
  const apps = [...appliedJobIds]
    .map((id) => all.find((j) => j.job_id === id))
    .filter((j): j is JobDetailResponse => j !== undefined)
    .map((job) => ({
      job: toSummary({ ...job, applied: true }),
      applied_at: appliedAt.get(job.job_id) ?? new Date().toISOString(),
      resume_filename: (resumeOverride ?? DEMO_RESUME).filename,
      resume_sha256: (resumeOverride ?? DEMO_RESUME).sha256,
      letter_version_used: appliedLetterVersion.get(job.job_id) ?? null,
      resume_replaced_since: false,
    }));
  return { applications: apps, total: apps.length };
}

export function demoMarkApplied(
  jobId: string,
  letterVersion: number | null,
): void {
  appliedJobIds.add(jobId);
  appliedAt.set(jobId, new Date().toISOString());
  appliedLetterVersion.set(jobId, letterVersion);
}

export function demoUnmarkApplied(jobId: string): void {
  appliedJobIds.delete(jobId);
  appliedAt.delete(jobId);
  appliedLetterVersion.delete(jobId);
}

// ---------------- Hidden lists / queries / resume mirror writers ----------------

export function demoHiddenLists(): HiddenListsResponse {
  return getHiddenListsState();
}

export function demoSetHiddenList(
  kind: "companies" | "title_keywords",
  items: string[],
): string[] {
  const state = getHiddenListsState();
  state[kind] = items;
  return items;
}

export function demoQueriesList(): QueryListResponse {
  return {
    queries: getQueriesState(),
    next_refresh_allowed_at: null,
  };
}

export function demoCreateQuery(body: {
  what?: string;
  where?: string;
}): SavedQuery {
  const q: SavedQuery = {
    query_id: `q-demo-${Math.random().toString(36).slice(2, 8)}`,
    what: body.what ?? "",
    where: body.where ?? "",
    enabled: true,
    created_at: new Date().toISOString(),
  };
  getQueriesState().push(q);
  return q;
}

export function demoUpdateQuery(
  id: string,
  body: { what?: string; where?: string; enabled?: boolean },
): SavedQuery | null {
  const state = getQueriesState();
  const idx = state.findIndex((q) => q.query_id === id);
  if (idx === -1) return null;
  state[idx] = {
    ...state[idx],
    ...(body.what !== undefined && { what: body.what }),
    ...(body.where !== undefined && { where: body.where }),
    ...(body.enabled !== undefined && { enabled: body.enabled }),
  };
  return state[idx];
}

export function demoDeleteQuery(id: string): void {
  const state = getQueriesState();
  const idx = state.findIndex((q) => q.query_id === id);
  if (idx !== -1) state.splice(idx, 1);
}

export function demoResume(): ResumeMetadata {
  return resumeOverride ?? DEMO_RESUME;
}

export function demoReplaceResume(
  filename: string | null,
  sizeBytes: number | null,
): ResumeUploadResponse {
  resumeOverride = {
    filename: filename ?? DEMO_RESUME.filename,
    size_bytes: sizeBytes ?? DEMO_RESUME.size_bytes,
    uploaded_at: new Date().toISOString(),
    sha256: DEMO_RESUME.sha256,
  };
  return { ...resumeOverride, prefilled_fields: [] };
}

// ---------------- Small synthetic generator for fake polling ----------------

const PHASE_SEQUENCE = [
  "Reading the job description…",
  "Searching your resume…",
  "Committing strategy…",
  "Critiquing the draft…",
  "Saving the letter…",
];

/** Returns the phase string corresponding to how many seconds the
 *  fake generation has been "running". Tuned so the whole sequence
 *  fits in ~25-30 seconds of fake-loading time. */
export function demoPhaseAt(elapsedMs: number): string {
  const stepMs = 5_000;
  const idx = Math.min(
    PHASE_SEQUENCE.length - 1,
    Math.floor(elapsedMs / stepMs),
  );
  return PHASE_SEQUENCE[idx];
}

export const DEMO_GENERATION_TOTAL_MS = 25_000;

/** Build the LetterGenerationStatus the polling endpoint should
 *  return at a given elapsed time. */
export function demoGenerationStatus(
  jobId: string,
  generationId: string,
  startedAtMs: number,
): LetterGenerationStatus {
  const elapsed = Date.now() - startedAtMs;
  const startedAt = new Date(startedAtMs).toISOString();

  if (elapsed < DEMO_GENERATION_TOTAL_MS) {
    return {
      generation_id: generationId,
      status: "running",
      started_at: startedAt,
      completed_at: null,
      letter: null,
      error: null,
      phase: demoPhaseAt(elapsed),
    };
  }

  const letter = demoFakeLetter(jobId);
  demoAppendLetter(jobId, letter);
  return {
    generation_id: generationId,
    status: "done",
    started_at: startedAt,
    completed_at: new Date().toISOString(),
    letter,
    error: null,
    phase: "Saved.",
  };
}

/** What POST /letters returns immediately. */
export function demoStartGeneration(): GenerateLetterResponse {
  return {
    generation_id: `demo-gen-${Math.random().toString(36).slice(2, 10)}`,
    status: "pending",
    estimated_seconds: 30,
  };
}

// ---------------- Polish (passes user's text through with tiny tweak) ----------------

export function demoPolish(text: string): WhyInterestedResponse {
  // Mild "polish" — just normalise whitespace and capitalise the first
  // letter. The disclaimers in the dialog explain that this isn't a
  // real grammar fix.
  const normalised = text
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^./, (c) => c.toUpperCase());
  return {
    text: normalised,
    word_count: normalised.split(/\s+/).filter(Boolean).length,
  };
}
