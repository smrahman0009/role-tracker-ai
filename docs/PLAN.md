# Role Tracker — Project Plan

## Context
The user is job-hunting for data science, ML, AI engineer, and software developer and other roles in Canada or anywhere in the world. Manually searching Adzuna every day, scoring each posting against his resume, tailoring a cover letter per job, and tracking which jobs he has already applied to is repetitive and slow.

**Goal:** a daily automated pipeline that:
1. Fetches fresh Canadian jobs from the Adzuna API using user-defined filters.
2. Scores each job against the user's resume using OpenAI embeddings.
3. Picks the top N matches, tailors the user's base cover letter to each using a Claude agent (Anthropic API).
4. Emails the user a daily digest containing each top job's description, tailored cover letter, resume, and apply link.
5. Remembers jobs it has already sent so the user never gets duplicates.
6. Runs automatically every morning on Azure, deployed via Docker + GitHub Actions CI/CD.

**Why this project / desired outcome:**
- Save hours per day of manual job searching.
- Treat it as a real-world professional DevOps project (Docker, CI/CD, OIDC auth, cloud-native scheduling) — not a throwaway script.
- Build incrementally and locally first so each piece is understood before moving to cloud.

## Architecture (at a glance)
```
┌─────────────────────────────────────────────────────────────────┐
│  Azure Container Apps Job (cron: daily 08:00 America/Toronto)  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Docker container running src/role_tracker/pipeline.py     │ │
│  │                                                           │ │
│  │  1. Fetch jobs (Adzuna API)                               │ │
│  │  2. Embed + score vs resume (OpenAI embeddings)           │ │
│  │  3. Filter out already-sent (Azure Table Storage)         │ │
│  │  4. Tailor cover letter for top N (Claude agent)          │ │
│  │  5. Send email digest (Gmail SMTP)                        │ │
│  │  6. Mark jobs as sent (Azure Table Storage)               │ │
│  └───────────────────────────────────────────────────────────┘ │
│         ↑ secrets from Azure Key Vault via managed identity    │
└─────────────────────────────────────────────────────────────────┘
       ↑ image pulled from Azure Container Registry
       │
┌──────────────────────────────────────────────────────────────┐
│  GitHub Actions CI/CD                                        │
│  - on push to main: lint → test → build image → push to ACR │
│  - deploy: update ACA Job to new image tag                  │
│  - auth: OIDC federated credential (no long-lived secrets)  │
└──────────────────────────────────────────────────────────────┘
```

## Tech stack (decided)
| Concern | Choice |
|---|---|
| Language / runtime | Python 3.12 |
| Job API | Adzuna (Canada) |
| Embeddings | OpenAI (`text-embedding-3-small`) |
| Cover letter agent | Anthropic Claude (`claude-sonnet-4-6`; extended thinking off initially) |
| Matching | Cosine similarity over resume + job embeddings |
| Dedupe store | Azure Table Storage (local: JSON file) |
| Resume / cover letter storage | Azure Blob Storage (local: `data/` folder) |
| Email | Gmail SMTP with app password |
| Containerization | Docker (multi-stage, slim image) |
| Hosting + scheduling | Azure Container Apps Jobs (cron trigger) |
| Secrets | Azure Key Vault + managed identity (local: `.env`) |
| CI/CD | GitHub Actions with OIDC federated credential to Azure |
| Registry | Azure Container Registry (ACR) |
| Package / venv manager | `uv` |
| Tests | `pytest` |
| Lint + format | `ruff` (replaces black + flake8 + isort) |
| Data models | `pydantic` v2 (+ `pydantic-settings` for config) |
| Config | `pydantic-settings` reading `.env` + a `config.yaml` for filters |

## Development practices (locked in)
These are the modern practices the project will follow from day one. They are explicitly chosen to balance professional quality with fast, unblocked progress — nothing here should create debugging-hell.

### Tooling
- **`uv`** — replaces `pip` + `venv` + `pyenv`. Same commands as pip but 10–100× faster. If it ever breaks, fall back to `pip` in seconds.
- **`ruff`** — replaces `black` + `flake8` + `isort`. One tool for linting AND formatting. Run on save / in CI.
- **`pyproject.toml`** — single source of truth for dependencies, project metadata, and tool config. No `requirements.txt`, no `setup.py`, no `setup.cfg`.

### Code style
- **`src/` layout** — already in the repo structure. Prevents common import bugs.
- **Type hints everywhere** — every function signature gets types. No `mypy` strict mode yet (adds friction); types are for readability + IDE autocomplete.
- **Pydantic v2 models** for all structured data: config, job postings, agent step inputs/outputs, email payloads. No raw dicts flying around.
- **Dependency injection** — pass clients (OpenAI, Adzuna, email sender) into functions as arguments. Never import them as module-level singletons. Makes testing trivial and keeps modules decoupled.
- **Protocols / ABCs** for swappable implementations (e.g., `SentJobsStore` with `JsonFileStore` + `AzureTableStore`).

### LLM / agent practices
- **Structured outputs** — OpenAI steps use `response_format=json_schema`; Claude steps use tool use with Pydantic-defined input schemas to force structured JSON responses. Never parse free-text JSON from either model.
- **Prompts as versioned files** in `tailoring/prompts/*.md` — not hardcoded strings. Easier to iterate, diff, and review.
- **LLM call logging** — every LLM call (prompt, response, model, tokens, cost, latency) appended to a local JSONL file (`data/llm_calls.jsonl`). Essential for debugging agent behavior and tracking spend.

### Secrets & config
- **`.env` for local** (git-ignored), **Azure Key Vault + managed identity for prod**.
- **`.env.example`** committed as documentation of every required variable.
- **`pydantic-settings`** to load and validate config at startup — fail fast if anything is missing.

### Tools deliberately deferred (add only when needed)
`mypy`/`pyright` strict typing · `pre-commit` hooks · `VCR.py` test recording · `tenacity` retries · Dependabot/Renovate · async/await. Each of these is good practice but adds friction. Add them when there's a concrete reason, not upfront.

## Build phases (local-first, deploy-last)

### Phase 1 — Project scaffolding
- Python package skeleton (`src/role_tracker/__init__.py`), `.gitignore`, `.env.example`, `pyproject.toml`, `README.md`.
- `uv`-managed virtual environment.
- `ruff` + `pytest` configuration inside `pyproject.toml`.
- **Done when:** `python -c "import role_tracker"` works; `pytest` runs cleanly.

### Phase 2 — Adzuna client
- `src/role_tracker/jobs/adzuna.py`, `config.py`, `config.yaml`, `scripts/run_fetch.py`.
- Unit test with a recorded fixture.
- **Done when:** `python scripts/run_fetch.py` prints real Canadian jobs.

### Phase 3 — Resume parsing + embedding matching
- `resume/parser.py` (PDF → text), `matching/embeddings.py`, `matching/scorer.py`.
- Cache resume embedding locally.
- **Done when:** top 5 output looks genuinely relevant.

### Phase 4 — Cover letter tailoring (LLM agent)

**Why agent, not deterministic pipeline**

The alternative to an agent is a deterministic pipeline: a fixed sequence of rules and templates that processes every job the same way. For a narrow, well-defined role that approach can work. It doesn't work here.

The roles being applied to — data scientist, ML engineer, software developer, AI engineer — share a label but not a job. Two "Senior Data Scientist" postings at similar-looking companies can require completely different cover letter angles: one is building a recommendation system (the letter should emphasize ML systems, embeddings, real-time serving), another is building an experimentation platform (the letter should emphasize A/B testing, causal inference, statistical rigor). A startup DS role wants evidence of business impact and moving fast. A research role wants depth and methodological rigour. The same pattern repeats across software developer roles: backend API work, data engineering, infrastructure, and systems programming all carry the same title but need different positioning.

A deterministic pipeline handles this in one of two ways, both bad: it either writes a generic letter that fits no specific role well, or it requires manually coding a branching rule tree ("if job mentions recommendation systems, highlight X; if job mentions experimentation, highlight Y") that grows indefinitely and still misses combinations it wasn't programmed for.

An agent solves this differently. It reads each job description, reasons about what that specific role is actually asking for, retrieves the strongest matching evidence from the resume on demand, and writes a letter calibrated to those signals — all without pre-programmed category rules. The adaptation happens at inference time, driven by the content of the job itself. Jobs within the same category can be different enough that this reasoning step is the difference between a letter that resonates and one that sounds copy-pasted.

The tradeoffs are real and accepted: higher token cost per letter (~5–8× vs. single-shot), less byte-for-byte predictable output, harder to debug when quality varies. The alternative — a rule tree that never fully covers the variation in real job postings and requires manual updates as new role types appear — has worse tradeoffs for this use case.

This phase also doubles as a hands-on learning exercise for real LLM-agent patterns: tool use, multi-step orchestration, structured outputs between steps, and self-critique loops — patterns that transfer directly to LangGraph, the Anthropic Agents SDK, and any future agent work.

**Agent steps (each step = its own LLM call with a focused role):**
1. **Extract** — parse the job description into structured JSON: must-have skills, nice-to-haves, responsibilities, company signals.
2. **Match** — compare that JSON against the resume; pick the 2–3 strongest evidence points (real projects/experience, no filler).
3. **Draft** — write the cover letter (~300 words) in the user's voice, using only the matched evidence + base cover letter template.
4. **Critique** — score the draft against a rubric: addresses top requirements? sounds like the user? any generic filler or hallucinated claims?
5. **Revise** — rewrite based on the critique. Loop at most 1–2 times.

**Implementation: Claude API (Anthropic SDK)**
- Model: `claude-sonnet-4-6`. Extended thinking disabled initially; enable only if critique/revise quality is insufficient.
- Each step is a separate `client.messages.create()` call — no orchestration framework, just Python.
- `search_resume(query)` is implemented as a Claude tool (defined via the Anthropic SDK's `tools=` parameter). The agent calls it to retrieve relevant resume chunks on demand rather than seeing the whole resume every step.
- Structured outputs between steps are enforced by defining each tool's `input_schema` as a Pydantic model's JSON schema — Claude must populate that schema to "call" the tool, giving us typed, validated data at each step boundary.
- Per-step prompts stored in `tailoring/prompts/*.md` — not hardcoded strings.
- `tailoring/agent.py` is the orchestrator: calls each step in order, passes structured output forward, enforces the max-iterations guard on the critique→revise loop.
- Every Claude call (prompt, response, model, input tokens, output tokens, latency) logged to `data/llm_calls.jsonl`.

**Module layout:**
```
tailoring/
├── agent.py           # orchestrator (the loop)
├── steps/
│   ├── extract.py
│   ├── match.py
│   ├── draft.py
│   └── critique.py
├── tools/
│   └── resume_search.py
└── prompts/
    ├── extract.md
    ├── match.md
    ├── draft.md
    ├── critique.md
    └── revise.md
```

**Dependencies:** `anthropic` SDK added to `pyproject.toml`. OpenAI SDK is still present for Phase 3 embeddings (`text-embedding-3-small`) — only the tailoring agent uses Claude.

**Done when:** output reads as send-worthy AND the agent's intermediate JSON (extracted requirements, matched evidence, critique notes) is inspectable in logs for debugging.

**Done when:** output reads as send-worthy AND the agent's intermediate JSON (extracted requirements, matched evidence, critique notes) is inspectable in logs for debugging.

### Phase 5 — Email digest
- `email/sender.py` (Gmail SMTP) + Jinja2 HTML template.
- **Done when:** a clean-looking digest arrives in inbox.

### Phase 6 — Dedupe store
- Abstract `SentJobsStore` with `JsonFileStore` (local) and `AzureTableStore` (prod) impls.
- **Done when:** two runs in a row produce zero duplicates.

### Phase 7 — End-to-end pipeline
- `pipeline.py` + `__main__.py` → `python -m role_tracker`.
- Structured JSON logging to stdout.
- **Done when:** one command runs the full pipeline and emails a digest.

### Phase 8 — Docker
- Multi-stage Dockerfile, non-root user, `.dockerignore`.
- **Done when:** `docker run --env-file .env role-tracker:local` runs end-to-end.

### Phase 9 — Azure infrastructure (one-time)
- Resource group, ACR, Storage (Table + Blob), Key Vault, Container Apps env + Job with cron, managed identity.
- Documented in `docs/azure-setup.md`.
- **Done when:** `az containerapp job start` runs and emails a digest.

### Phase 10 — GitHub Actions CI/CD
- `ci.yml` (lint + test on push/PR), `deploy.yml` (build + push + deploy on main).
- OIDC federated credential — no long-lived secrets.
- Branch protection on `main`.
- **Done when:** pushing to `main` ships a new image automatically.

## Repo structure (final)
```
role_tracker_ai/
├── .github/workflows/          # ci.yml, deploy.yml
├── src/role_tracker/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── pipeline.py
│   ├── jobs/adzuna.py
│   ├── resume/parser.py
│   ├── matching/{embeddings,scorer}.py
│   ├── tailoring/               # agent.py, steps/, tools/, prompts/
│   ├── email/{sender,templates/}
│   └── storage/{sent_jobs,blob}.py
├── scripts/
├── tests/
├── data/                       # local-only, gitignored
├── docs/                       # PLAN.md, azure-setup.md
├── config.yaml
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Deliberately NOT doing
- Web portal / UI (filters in `config.yaml`)
- Airflow / Prefect (one daily job → ACA Jobs cron is right-sized)
- Terraform / Bicep (one-time infra, markdown doc is enough for v1)
- Database (Table + Blob are plenty)
- Monitoring stack (ACA logs are fine for v1)
- Retries / DLQs (pipeline is idempotent; tomorrow covers failures)

## Verification end-to-end
- **Local:** `python -m role_tracker` → digest arrives; rerun → zero duplicates.
- **Docker:** `docker run --env-file .env role-tracker:local` → same as local run.
- **Azure manual:** `az containerapp job start` → email + rows in Azure Table.
- **CI/CD:** push to `main` → image built, pushed, ACA Job updated, next scheduled run uses it.

## Estimated effort

### Phase 1–10 (personal pipeline)
~8–10 hours focused work across sessions. Phases 1–7 (local) ≈ 5–6h (Phase 4 agent adds ~1–2h over a single-shot prompt). Phases 8–10 (Docker + Azure + CI/CD) ≈ 3–4h.

### SaaS expansion (all phases below)
~40–55 hours additional work across sessions. See breakdown in the SaaS section below.

---

## Future: SaaS Expansion

Once the personal pipeline is stable and well-understood, the project will be expanded into a multi-user product where anyone can sign up, set their preferences, and receive daily tailored job digests.

### Product vision
- Users create an account and set their job search preferences (role types, locations, keywords).
- Each user uploads their own resume.
- The pipeline runs per-user daily, fetching jobs matched to their preferences, tailoring cover letters, and sending a personalized digest.
- A web dashboard lets users view past digests, update preferences, and manage their account.

### Architecture

```
User's browser
      ↕
React app  →  Azure Static Web Apps     (HTML/JS/CSS, no server, CI/CD from GitHub)
      ↕  REST API (HTTPS)
FastAPI app  →  Azure Container Apps    (Python backend, one container — monolithic v1)
      ↕
PostgreSQL  →  Azure Database for PostgreSQL Flexible Server   (per-user rows)
Blob Storage →  Azure Blob Storage      (per-user resume files)
Auth  →  Auth0 or Azure AD B2C          (JWT-based, do not roll custom auth)
```

### Tech stack additions
| Concern | Choice |
|---|---|
| Frontend | React (TypeScript) |
| Frontend hosting | Azure Static Web Apps |
| Backend framework | FastAPI (extends existing Python codebase) |
| Backend hosting | Azure Container Apps (same as personal pipeline) |
| Database | Azure PostgreSQL Flexible Server |
| Auth | Auth0 or Azure AD B2C |
| Per-user file storage | Azure Blob Storage (existing) |

### Why monolithic backend first (not microservices)
Starting with a single FastAPI container on ACA keeps deployment simple and identical to the personal pipeline you already know. Split into microservices only when there is a concrete scaling reason (e.g. the matching service needs independent scaling). Premature splitting adds operational cost with no benefit at v1.

### SaaS build phases

#### Phase S1 — Backend API skeleton
- FastAPI app with health check, project structure, Dockerfile.
- PostgreSQL schema: `users`, `preferences`, `sent_jobs` tables.
- Local dev with Docker Compose (API + Postgres).
- **Done when:** `GET /health` returns 200; migrations run cleanly.

#### Phase S2 — Auth
- Integrate Auth0 (or Azure AD B2C): sign-up, login, JWT validation middleware.
- `/me` endpoint returns authenticated user profile.
- **Done when:** protected routes reject unauthenticated requests.

#### Phase S3 — User preferences + resume upload
- `PUT /preferences` — store job filters (roles, locations, keywords) per user.
- `POST /resume` — upload PDF to Azure Blob, store reference in PostgreSQL.
- **Done when:** user can upload a resume and save preferences via API.

#### Phase S4 — Per-user pipeline execution
- Refactor personal pipeline to accept a `user_id` and pull config from PostgreSQL instead of `config.yaml`.
- ACA scheduled job loops over all active users and runs the pipeline per user.
- **Done when:** two test users each receive their own personalized digest.

#### Phase S5 — React frontend
- Pages: sign-up/login, preferences form, resume upload, digest history.
- Calls the FastAPI REST API with Auth0 JWT.
- Deploy to Azure Static Web Apps.
- **Done when:** end-to-end user journey works in the browser.

#### Phase S6 — Multi-tenant Azure infra + CI/CD
- Separate resource group for SaaS infra.
- Extend GitHub Actions to build and deploy both the API container and the React app.
- **Done when:** push to `main` ships both frontend and backend automatically.

### SaaS estimated effort
| Phase | Effort |
|---|---|
| S1 — API skeleton + DB schema | 3–4h |
| S2 — Auth integration | 4–6h |
| S3 — Preferences + resume upload | 3–4h |
| S4 — Per-user pipeline refactor | 4–6h |
| S5 — React frontend | 12–16h |
| S6 — Multi-tenant infra + CI/CD | 5–8h |
| Buffer (debugging, integration) | 8–10h |
| **Total** | **~40–55h** |
