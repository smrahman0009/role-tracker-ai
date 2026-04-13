# Role Tracker AI — Project Plan

## Context
The user is job-hunting for data science, ML, AI engineer, and software developer and other roles in Canada or anywhere in the world. Manually searching Adzuna every day, scoring each posting against his resume, tailoring a cover letter per job, and tracking which jobs he has already applied to is repetitive and slow.

**Goal:** a daily automated pipeline that:
1. Fetches fresh Canadian jobs from the Adzuna API using user-defined filters.
2. Scores each job against the user's resume using OpenAI embeddings.
3. Picks the top N matches, tailors the user's base cover letter to each using an OpenAI chat model.
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
│  │  4. Tailor cover letter for top N (OpenAI chat)           │ │
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
| LLM / embeddings | OpenAI (`text-embedding-3-small`, `gpt-4o-mini` or similar) |
| Matching | Cosine similarity over resume + job embeddings |
| Dedupe store | Azure Table Storage (local: JSON file) |
| Resume / cover letter storage | Azure Blob Storage (local: `data/` folder) |
| Email | Gmail SMTP with app password |
| Containerization | Docker (multi-stage, slim image) |
| Hosting + scheduling | Azure Container Apps Jobs (cron trigger) |
| Secrets | Azure Key Vault + managed identity (local: `.env`) |
| CI/CD | GitHub Actions with OIDC federated credential to Azure |
| Registry | Azure Container Registry (ACR) |
| Tests | pytest |
| Lint / format | ruff + black |
| Config | `pydantic-settings` reading `.env` + a `config.yaml` for filters |

## Build phases (local-first, deploy-last)

### Phase 1 — Project scaffolding
- Python package skeleton, `.gitignore`, `.env.example`, `requirements.txt`, `pyproject.toml`, `README.md`.
- ruff, black, pytest configs.
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
Built as a multi-step agent, not a single prompt, so the project doubles as a hands-on LLM-agent learning exercise.

**Agent steps (each step = its own LLM call with a focused role):**
1. **Extract** — parse the job description into structured JSON: must-have skills, nice-to-haves, responsibilities, company signals.
2. **Match** — compare that JSON against the resume; pick the 2–3 strongest evidence points (real projects/experience, no filler).
3. **Draft** — write the cover letter (~300 words) in the user's voice, using only the matched evidence + base cover letter template.
4. **Critique** — score the draft against a rubric: addresses top requirements? sounds like the user? any generic filler or hallucinated claims?
5. **Revise** — rewrite based on the critique. Loop at most 1–2 times.

**Agent building blocks to implement:**
- Tool use: a `search_resume(query)` tool so the agent retrieves relevant resume chunks on demand instead of seeing the whole resume every call.
- Structured outputs (JSON schemas) between steps — not free text.
- A small orchestration layer (`tailoring/agent.py`) that runs the extract → match → draft → critique → revise loop with a max-iterations guard.
- Per-step prompts kept in `tailoring/prompts/` as separate files (easier to iterate and diff).

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
└── prompts/*.md
```

**Done when:** output reads as send-worthy AND the agent's intermediate JSON (extracted requirements, matched evidence, critique notes) is inspectable in logs for debugging.

**Tradeoff accepted:** ~5–8× OpenAI cost per letter vs. single-shot, in exchange for learning real agent patterns (tool use, multi-step orchestration, self-critique) that transfer to LangGraph / OpenAI Agents SDK / etc.

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
- **Done when:** `docker run --env-file .env role-tracker-ai:local` runs end-to-end.

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
├── requirements.txt
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
- **Docker:** `docker run --env-file .env role-tracker-ai:local` → same as local run.
- **Azure manual:** `az containerapp job start` → email + rows in Azure Table.
- **CI/CD:** push to `main` → image built, pushed, ACA Job updated, next scheduled run uses it.

## Estimated effort
~8–10 hours focused work across sessions. Phases 1–7 (local) ≈ 5–6h (Phase 4 agent adds ~1–2h over a single-shot prompt). Phases 8–10 (Docker + Azure + CI/CD) ≈ 3–4h.
