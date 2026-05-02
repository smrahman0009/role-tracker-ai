# Role Tracker AI

An end-to-end job-search assistant. Searches live job boards, ranks postings against your resume with embeddings, drafts a tailored cover letter through a multi-step Claude agent, and tracks every application — all in one web app.

Built as a portfolio-grade AI engineering project: a typed Python backend with a React frontend, an agentic LLM workflow (plan → critique → revise), prompt caching, retrieval-style structured extraction, and a usage / cost dashboard so the bills don't surprise you.

## What it does

- **Live job search.** Fetches postings via JSearch (Google for Jobs), dedupes across saved searches, and applies user-defined exclusions on companies, title keywords, and recruiters.
- **Resume-aware ranking.** OpenAI `text-embedding-3-small` for both resume and job descriptions; cosine similarity surfaces the strongest matches first. Resume embeddings are content-hashed and cached on disk.
- **Agentic cover-letter generation.** A Claude Sonnet planner commits to a strategy, drafts the letter using tools (resume facts, JD highlights, profile contact block), then a Claude Haiku critic scores it against a rubric and the planner revises if a category fails. Stable system prompts are wrapped in Anthropic's prompt-cache blocks.
- **Why-interested + grammar polish.** One-click, ~3-second Haiku passes for short application-form answers and final-edit grammar fixes.
- **URL → posting extractor.** Pasting an arbitrary job URL tries three tiers in order: ATS JSON APIs (Workable, Greenhouse, Lever), schema.org `JobPosting` JSON-LD, then a Trafilatura fallback — followed by an LLM refinement pass that pulls the actual hiring company out of recruiter/aggregator pages.
- **Application tracker.** Marking a job applied snapshots the resume filename + SHA-256 and the letter version used at apply time. The applications page surfaces a "now replaced" tag if you've since uploaded a different resume.
- **Usage & quota dashboard.** Per-user, per-month rollups of JSearch fetches, OpenAI embeddings, and each Anthropic feature, with cost estimates and a JSearch quota progress bar. Six months of history retained.

## Stack

**Backend** — Python 3.12, FastAPI, Pydantic v2, `uv`, `ruff`, `pytest`. Anthropic + OpenAI SDKs. JSON-file-backed storage today behind `Protocol` interfaces, designed to swap to Cosmos DB without route changes.

**Frontend** — React 19, TypeScript, Vite, TanStack Query, Tailwind CSS v4, lucide icons. Document Picture-in-Picture for the floating cover-letter editor on supported browsers.

**LLM tooling** — Claude Sonnet 4.6 (planner / refine), Claude Haiku 4.5 (critic / polish / why-interested / URL refine), prompt caching on stable prefixes, structured tool calling.

## Repository layout

```
src/role_tracker/
  api/              FastAPI routes, Pydantic schemas, bearer-token middleware
  applied/          Per-user "applied" records (applied_at, resume snapshot, letter version)
  cover_letter/     Agent loop, planner, critic, refine, polish, tools
  jobs/             JSearch client, pipeline, URL extractor, snapshot cache
  letters/          Versioned letter store, PDF/DOCX rendering, header injection
  matching/          Embedder + scorer
  resume/           Upload, parse, store
  screening/         Why-interested generate + polish
  usage/             Per-user monthly rollups + cost estimates
  users/             Profile store (YAML)
frontend/
  src/pages/        JobList, JobDetail, Applications, ManualJobs, Usage, Settings
  src/components/   JobCard, FitBadge, AddManualJobDialog, ResumeCard, …
  src/hooks/        useJobs, useUsage, useResume, useLetters, …
docs/               PLAN.md, plan_search_first_home.md, agentic AI tutorial
tests/              342 backend tests across api/, jobs/, letters/, cover_letter/, …
```

## Quick start (local)

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Backend deps
uv venv
uv pip install -e ".[dev]"

# 3. Secrets
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, OPENAI_API_KEY, JSEARCH_RAPIDAPI_KEY

# 4. Backend
uv run uvicorn role_tracker.api.main:app --reload

# 5. Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

Run the test suite with `uv run pytest`.

## Status

The web app is feature-complete locally. Remaining work is deployment-side: Docker packaging, Azure Container Apps infrastructure, GitHub Actions CI/CD with OIDC, and a scheduled daily-refresh job. An optional email digest, a logged-out landing page, and soft monthly-cap enforcement on the usage dashboard are tracked as polish items.

See [docs/PLAN.md](docs/PLAN.md) for the original phased plan and [docs/plan_search_first_home.md](docs/plan_search_first_home.md) for the search-first redesign.
