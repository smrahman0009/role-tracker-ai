# Role Tracker AI

[![CI](https://github.com/smrahman0009/role-tracker-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/smrahman0009/role-tracker-ai/actions/workflows/ci.yml)
[![Deploy](https://github.com/smrahman0009/role-tracker-ai/actions/workflows/deploy.yml/badge.svg)](https://github.com/smrahman0009/role-tracker-ai/actions/workflows/deploy.yml)

An end-to-end job-search assistant. Searches live job boards, ranks postings against your resume with embeddings, drafts a tailored cover letter through a multi-step Claude agent, and tracks every application, all in one web app.

Typed Python backend (FastAPI), typed React frontend, agentic LLM pipeline (plan → critique → revise) with prompt caching, retrieval-style structured extraction, a usage / cost dashboard, and a cloud-native AWS deployment with CI/CD on every push to `main`.

> **Status:** deployed and live on AWS · 401 tests · CI/CD enabled · [Phase E backlog](#status--next-steps)

## What it does

- **Live job search.** Fetches postings via JSearch (Google for Jobs), dedupes across saved searches, and applies user-defined exclusions on companies, title keywords, and recruiters.
- **Resume-aware ranking.** OpenAI `text-embedding-3-small` for both resume and job descriptions; cosine similarity surfaces the strongest matches first. Resume embeddings are content-hashed and cached on disk.
- **Agentic cover-letter generation.** A Claude Sonnet planner commits to a strategy, drafts the letter using tools (resume facts, JD highlights, profile contact block), then a Claude Haiku critic scores it against a rubric and the planner revises if a category fails. Stable system prompts are wrapped in Anthropic's prompt-cache blocks. Triggered by a single Generate dialog: leave it empty for one-click, or supply optional steering (free-text instruction, a paste-in style template, opt-in extended-thinking) — same dialog handles refining the current draft via a mode toggle.
- **Why-interested + grammar polish.** One-click, ~3-second Haiku passes for short application-form answers and final-edit grammar fixes.
- **URL → posting extractor.** Pasting an arbitrary job URL tries three tiers in order: ATS JSON APIs (Workable, Greenhouse, Lever), schema.org `JobPosting` JSON-LD, then a Trafilatura fallback, followed by an LLM refinement pass that pulls the actual hiring company out of recruiter/aggregator pages.
- **Application tracker.** Marking a job applied snapshots the resume filename + SHA-256 and the letter version used at apply time. The applications page surfaces a "now replaced" tag if you've since uploaded a different resume.
- **Usage & quota dashboard.** Per-user, per-month rollups of JSearch fetches, OpenAI embeddings, and each Anthropic feature, with cost estimates and a JSearch quota progress bar. Six months of history retained.

## Stack

**Backend.** Python 3.12, FastAPI, Pydantic v2, `uv`, `ruff`, `pytest`. Anthropic + OpenAI SDKs. Storage abstracted behind `Protocol` interfaces with two interchangeable implementations: JSON-on-disk (dev) and AWS-native (DynamoDB + S3 + SSM Parameter Store) selected at runtime by a single env var.

**Frontend.** React 19, TypeScript, Vite, TanStack Query, Tailwind CSS v4, lucide icons. Document Picture-in-Picture for the floating cover-letter editor on supported browsers.

**LLM tooling.** Claude Sonnet 4.6 (planner / refine), Claude Haiku 4.5 (critic / polish / why-interested / URL refine), prompt caching on stable prefixes, structured tool calling.

**Cloud / deployment.** Single-container Docker image deployed to AWS EC2 (live). Cloud-native storage on Amazon DynamoDB (5 tables) and S3 (resume PDFs). Secrets in SSM Parameter Store, fetched at container startup via the EC2 IAM role. **CI/CD via GitHub Actions:** every push to `main` builds the image, pushes to ECR, and restarts the running container via SSM Run Command. Auth uses **OIDC federated credentials** so no static AWS keys live in GitHub Secrets. Infrastructure provisioning is reproducible from idempotent shell scripts in [`infra/`](infra/).

## Repository layout

```
src/role_tracker/
  api/              FastAPI routes, Pydantic schemas, bearer-token middleware,
                    production ASGI wrapper that mounts the SPA + API together
  applied/          Per-user "applied" records (applied_at, resume snapshot,
                    letter version)
  aws/              S3 + DynamoDB + SSM-backed implementations of every
                    storage Protocol; selected when STORAGE_BACKEND=aws
  cover_letter/     Agent loop, planner, critic, refine, polish, tools
  jobs/             JSearch client, pipeline, URL extractor, snapshot cache
  letters/          Versioned letter store, PDF/DOCX rendering, header injection
  matching/         Embedder + scorer
  resume/           Upload, parse, store
  screening/        Why-interested generate + polish
  usage/            Per-user monthly rollups + cost estimates
  users/            Profile store (YAML)
frontend/
  src/pages/        JobList, JobDetail, Applications, ManualJobs, Usage,
                    Settings, Login
  src/components/   JobCard, FitBadge, AddManualJobDialog, ResumeCard, ...
  src/hooks/        useJobs, useUsage, useResume, useLetters, ...
infra/              Idempotent shell scripts that provision every AWS
                    resource (ECR, S3, DynamoDB, SSM, IAM, EC2, OIDC)
.github/workflows/  ci.yml (lint + tests on every push) and
                    deploy.yml (build + push to ECR + restart EC2 on push to main)
docs/               See the linked docs in the Deployment section below
tests/              401 tests across api/, jobs/, letters/, cover_letter/,
                    aws/ (moto-mocked), ...
Dockerfile          Multi-stage build: Node bundles the SPA → uv resolves
                    Python deps → slim Python runtime as the final image
```

## Quick start (local)

```bash
# 1. Install uv + dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv && uv pip install -e ".[dev]"

# 2. Secrets
cp .env.example .env
# Fill in three keys. Links to where you get each one:
#   ANTHROPIC_API_KEY     https://console.anthropic.com/
#   OPENAI_API_KEY        https://platform.openai.com/api-keys
#   JSEARCH_RAPIDAPI_KEY  https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch

# 3. Backend
uv run uvicorn role_tracker.api.main:app --reload

# 4. Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Run the full test suite (~30 seconds): `uv run pytest`.
Lint: `uv run ruff check src tests`.

## Deployment

The whole AWS stack is reproducible from the [`infra/`](infra/) directory. Walkthrough docs:

- [`docs/aws-onboarding.md`](docs/aws-onboarding.md), one-time AWS account setup checklist (sign-up hardening, IAM admin user, CLI auth, SSH keys).
- [`docs/aws-deployment-plan.md`](docs/aws-deployment-plan.md), the master plan: target architecture, every infra script, every storage migration, expected cost.
- [`docs/docker-setup.md`](docs/docker-setup.md), Docker walkthrough explaining the multi-stage build, day-to-day commands, dev-vs-Docker mental model.
- [`docs/cicd-setup.md`](docs/cicd-setup.md), GitHub Actions setup with OIDC, what each workflow step does, rollback paths, cost.
- [`docs/operations.md`](docs/operations.md), operating the live deployment: token recovery, rotation, log inspection.

Once AWS CLI is authenticated, the entire stack provisions in eight idempotent scripts:

```bash
./infra/01-ecr.sh           # Docker image registry
./infra/02-s3.sh            # resume blob bucket
./infra/03-dynamodb.sh      # five DynamoDB tables (applied, letters, usage, queries, seen_jobs)
./infra/04-ssm.sh           # API keys → SSM Parameter Store
./infra/05-iam.sh           # least-privilege EC2 role + SSM Agent permissions
./infra/06-ec2.sh           # launch t2.micro with Docker bootstrap
./infra/07-deploy.sh        # build → push → restart (manual fallback; CI/CD takes over after 08)
./infra/08-github-oidc.sh   # GitHub Actions OIDC trust + deploy role
```

After that, `git push origin main` triggers an automatic build → push to ECR → SSM Run Command restart → smoke test, all gated by the test suite.

**Cost in practice:** ~$0/month in year 1 (everything fits inside the AWS Free Tier: t2.micro 12-month + always-free DynamoDB tier + SSM Parameter Store free tier). ~$10/month after the EC2 free tier expires.

## Status & next steps

**What's done.**

- **Phases A–D** from the deployment plan: AWS provisioning, cloud-native stores (DynamoDB + S3), SSM-loaded secrets, GitHub Actions CI/CD with OIDC.
- **Custom domain + HTTPS**: live at [`https://roletracker.app`](https://roletracker.app) via Cloudflare DNS / SSL.
- **Multi-user beta**: bearer-token middleware binds each token to one `user_id` and rejects cross-user paths with 403. Token mint / rotate / remove via [`infra/users/manage_users.py`](infra/users/manage_users.py). Three friend-testers onboarded.
- **Per-user daily cost cap** with optional per-user overrides — see [`docs/multi_user.md`](docs/multi_user.md).
- **Cover-letter Generate dialog** ([`docs/cover_letter_dialog_plan.md`](docs/cover_letter_dialog_plan.md)): single Generate button opens a dialog where the user can give an optional steering instruction, paste a style template, or toggle Anthropic's extended-thinking mode. Empty body works as one-click. Live progress phase labels during generation.
- **ATS-friendly contact header**: URLs render as plain text (`https://linkedin.com/...`) so resume scrapers parse them.

**Open follow-ups (none blocking).**

| Item | Why it's worth doing | Estimate |
|------|---------------------|----------|
| **Real-job prompt iteration** | Tune the agent's system prompt based on output quality on actual postings. Only meaningful after using the dialog on 3-5 real applications. | ~2 hrs |
| **Public demo mode** | A read-only `user_id=demo` with seeded sample data lets recruiters click through every screen without burning your API budget. | ~3 hrs |
| **Cloudflare Access** | Zero-trust gateway in front of the site so unauthorised visitors don't even see the login page. Free tier covers 50 users; defensible defer at 3 testers. | ~30 min |
| **Daily refresh job** | EventBridge rule that re-runs the matching pipeline overnight so the user wakes up to fresh ranked jobs. | ~1 hr |

None of these are required. The app is portfolio-ready and friend-tester-ready as it stands.

## Authorship

Designed and built by **Shaikh Mushfikur Rahman**, a data scientist and software developer based in Canada. This project started as a personal job-search tool and grew into a full demonstration of agentic LLM workflows, cloud-native AWS deployment, and CI/CD on GitHub Actions.

If you find this useful, fork it, learn from it, or adapt pieces into your own projects, that's exactly what it's here for. If you build on it in something public, a link back is appreciated. If you're a recruiter or fellow engineer who'd like to chat, the contacts below are the best way to reach me.

- LinkedIn: [linkedin.com/in/mushfikurrahman](https://www.linkedin.com/in/mushfikurrahman)
- Email: [shaikh.rahman.dev@gmail.com](mailto:shaikh.rahman.dev@gmail.com)

Released under the [MIT License](LICENSE).
