# Role Tracker — Operator's Handbook

> The single document an operator (you, your future self, a collaborator) reads to learn the system end-to-end. Skim it once. Bookmark it. Come back when something breaks.
>
> **Audience:** a developer who knows Python / HTTP / git / basic AWS at the concept level but has never seen this project. Where general tools come up (Docker, FastAPI, Anthropic), there's a one-line "what it is" + a link to its docs. Everything *project-specific* is explained in detail.
>
> **For history and context:** see [`docs/project_state.md`](project_state.md). For the original phase-by-phase plans, see the *Historical plans* section at the end.

---

## Table of contents

1. [What is Role Tracker?](#1-what-is-role-tracker)
2. [Architecture overview](#2-architecture-overview)
3. [Local development](#3-local-development)
4. [Deployment to AWS](#4-deployment-to-aws)
5. [User management](#5-user-management)
6. [Caps, costs, and quotas](#6-caps-costs-and-quotas)
7. [Operations cookbook](#7-operations-cookbook)
8. [Glossary](#8-glossary)
9. [Where to read deeper](#9-where-to-read-deeper)

---

## 1. What is Role Tracker?

**A job-search assistant for one user (you), with a small private beta for two friends.**

The user uploads a resume, saves search queries, and the system fetches matching jobs daily, ranks them by resume-fit, and helps draft a tailored cover letter for each one. The cover-letter writer is an LLM agent (Anthropic Claude) that reads the resume + job description, commits to a strategy, drafts, self-critiques, revises, and saves a numbered version. The user can re-run the whole thing with optional steering ("make it punchier", "follow this template") via a single Generate button.

Live at **https://roletracker.app**.

Three users today: `smrah` (admin / power user), `rafin_`, `ahasan_` (friend testers).

---

## 2. Architecture overview

### Components, end to end

```
Browser
   │  HTTPS via Cloudflare DNS + Cloudflare-Origin SSL
   ▼
┌──────────────────────────────────────────────────────────────┐
│ AWS EC2 t2.micro  (region: ca-central-1)                     │
│ ─────────────────                                             │
│ systemd unit "role-tracker.service"                          │
│   └─ Docker container (image: ECR :latest)                   │
│        ├─ FastAPI backend  (Python 3.12, uvicorn)            │
│        │   - Bearer-token middleware (multi-user)            │
│        │   - 30+ HTTP routes (jobs, letters, profile, ...)   │
│        │   - Background tasks for long-running agent loops   │
│        └─ Built React SPA  (served at "/")                   │
└────────┬─────────────────────────────────────────────────────┘
         │
   ┌─────┼─────────────────┐──────────────────┐──────────────┐
   ▼     ▼                 ▼                  ▼              ▼
 SSM   DynamoDB          S3              Anthropic       OpenAI
Param  ─────────         ───             ─────────       ──────
Store  5 tables:        resumes,        Claude Sonnet   text-
       applied,         letter PDFs,    + Haiku for     embedding-
secrets letters,        DOCX exports     generation +    3-small
+ token usage,                          refine + polish  for ranking
map    queries,                         (per-call)       jobs vs
       seen-jobs                                          resume
```

### What lives where

| Concern | Storage | Notes |
|---|---|---|
| **Bearer tokens** (multi-user auth) | SSM `APP_TOKENS` (JSON map) | Read at container startup. Restart to pick up changes. |
| **API keys** (Anthropic, OpenAI, JSearch) | SSM SecureStrings under `/role-tracker/` | Loaded into env vars at startup. |
| **User profiles** (resume path, queries, contact info) | YAML files inside the container at `users/{user_id}.yaml` | Editable through the API; persisted to disk inside the running container. |
| **Resumes** (PDF blobs) | S3 `role-tracker-data-{account}/resumes/{user_id}.pdf` | Uploaded via API, downloaded into a temp file when the agent runs. |
| **Letters** (saved versions) | DynamoDB `role-tracker-letters` (PK `user_id`, SK `job_id#version`) | Strategy + critique stored alongside the text. |
| **Jobs seen / ranked** | DynamoDB `role-tracker-seen-jobs` | Long-lived index per user; what the UI lists. |
| **Saved searches** | DynamoDB `role-tracker-queries` | One row per saved query per user. |
| **Applied jobs** | DynamoDB `role-tracker-applied` | Snapshot of resume + letter version at apply time. |
| **Usage rollups** (cost tracking) | DynamoDB `role-tracker-usage` | Per-month + per-day buckets per user. |
| **Daily cap state** | Same `role-tracker-usage` table — derived from today's bucket | Cap enforcement reads `get_today_cost_usd()`. |

### Code layout

```
src/role_tracker/
  api/         FastAPI app + routes + Pydantic schemas + bearer-token middleware
  applied/     Application records
  aws/         DynamoDB / S3 / SSM-backed Stores (selected when STORAGE_BACKEND=aws)
  cover_letter/ Agent loop + Refine + Polish + system prompts
  jobs/        JSearch fetch + dedup + filter
  letters/     LetterStore + PDF/DOCX rendering + header substitution
  matching/    OpenAI embeddings + cosine ranking
  resume/      PDF parsing
  screening/   Why-interested generator
  url_extract/ "Paste a URL → get the JD" extractor
  usage/       Per-feature cost tracking + daily cap enforcement
  users/       User profile model + YAML store
  config.py    Pydantic Settings (env vars)

frontend/src/
  components/  Reusable UI (Button, Card, Dialog, ...)
  hooks/       TanStack Query wrappers
  lib/         API client + auth + types
  pages/       JobListPage, JobDetailPage, LoginPage, ...
  auth/        AuthContext

infra/
  00-vars.sh         Shared variables (region, account ID, resource names)
  01-ecr.sh          Create ECR registry
  02-s3.sh           Create the resumes bucket
  03-dynamodb.sh     Provision the 5 DynamoDB tables
  04-ssm.sh          Upload secrets to SSM
  05-iam.sh          EC2 instance role
  06-ec2.sh          Launch the EC2 instance + security group
  07-deploy.sh       Build → push → restart  (the one you run all the time)
  08-github-oidc.sh  GitHub Actions OIDC trust setup (optional)
  users/manage_users.py  Mint / rotate / remove user tokens
```

### Two storage backends, picked at runtime

The system runs in **two modes**:

- `STORAGE_BACKEND=file` (dev default) — every store is JSON-on-disk under `data/`. Fast iteration, no AWS dependency. What you use locally.
- `STORAGE_BACKEND=aws` (prod, set in the systemd unit) — Stores swap to DynamoDB / S3 implementations. Same `Protocol` interfaces, same call sites, different concrete classes. What runs on EC2.

This means: code that's tested locally with file stores deploys unchanged to AWS. The factories in each `api/routes/*.py` read `Settings().storage_backend` and pick the implementation.

---

## 3. Local development

### One-time setup

You'll need:

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) — the Python package manager this project uses (faster, simpler than pip+venv)
- Node 20+ for the frontend
- A `.env` file with API keys

```bash
# Clone
git clone git@github.com:smrahman0009/role-tracker-ai.git
cd role-tracker-ai

# Backend deps + dev tools
uv sync --all-extras

# Frontend deps
cd frontend && npm install && cd ..

# .env file — copy the template and fill in real values
cp .env.example .env
# then edit .env and set:
#   ANTHROPIC_API_KEY=...
#   OPENAI_API_KEY=...
#   JSEARCH_RAPIDAPI_KEY=...
#   APP_TOKEN=                  ← leave empty for dev (no auth)
#   STORAGE_BACKEND=file        ← keep this for local dev
```

### Run the backend

```bash
uv run uvicorn role_tracker.api.main:app --reload --port 8000
```

[FastAPI](https://fastapi.tiangolo.com/) serves at http://localhost:8000. `--reload` restarts the server on every code change. Healthcheck: http://localhost:8000/api/health.

### Run the frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

[Vite](https://vitejs.dev/) serves at http://localhost:5173 with hot module reload. The frontend proxies API requests to `localhost:8000`.

### Run the tests

```bash
uv run pytest -q              # all backend tests, ~45s
uv run pytest tests/api/ -q   # just the API tests
uv run ruff check .           # linter
cd frontend && npx tsc -b     # frontend typecheck
```

The full suite is ~485 tests, all should pass.

### Most useful environment variables

Set in `.env` for local development. Same names work on prod (set via SSM there).

| Variable | What it does | Default |
|---|---|---|
| `STORAGE_BACKEND` | `file` or `aws` | `file` |
| `APP_TOKEN` | Single bearer token (dev / legacy) | empty (no auth) |
| `APP_TOKENS` | JSON map for multi-user mode | empty |
| `DAILY_COST_CAP_USD` | Global daily cost cap in dollars | `1.50` |
| `DAILY_COST_CAP_USD_OVERRIDES` | JSON map `{user_id: cap}` for per-user overrides | empty |
| `MAX_CHAT_TURNS` | Reserved (chat feature deferred) | `10` |
| `ANTHROPIC_API_KEY` | Anthropic API key | required for cover letters |
| `OPENAI_API_KEY` | OpenAI API key | required for embeddings |
| `JSEARCH_RAPIDAPI_KEY` | RapidAPI key | required for job fetching |

---

## 4. Deployment to AWS

### What gets deployed

The whole app — backend + built frontend — is packaged into a single Docker image. The image is pushed to AWS ECR. The EC2 instance pulls `:latest` and runs it as a systemd-managed Docker container.

### The one command you run

```bash
./infra/07-deploy.sh
```

That script does five things in order:

1. **Look up the EC2 instance's public IP** via `aws ec2 describe-instances` filtered by Name tag.
2. **Build the Docker image locally** with `docker buildx build --platform linux/amd64`. The platform flag forces an x86 build — without it, an Apple Silicon laptop produces an arm64 image that won't run on the x86 EC2 instance.
3. **Push to ECR** as `:latest`.
4. **SSH into EC2** and run `sudo systemctl restart role-tracker`. Systemd's start command is "stop → docker rm → docker pull :latest → docker run", so the restart pulls and runs the new image.
5. **Wait 15s, then hit `/api/health`** — the smoke test. Retries up to 5 times because a fresh `docker pull` can take 10-20s.

If any step fails, the script exits non-zero. Re-run after fixing.

### Typical workflow

```bash
# Make changes, commit, push to main
git add ...
git commit -m "..."
git push origin main

# Deploy
./infra/07-deploy.sh
```

The script reads from your local working tree, **not** from main. So whichever branch you're on gets deployed. Best practice: merge to `main`, push, then deploy from `main`. That way `main` is always "what's in prod."

### Rollback

There's no automated rollback. Two manual approaches:

```bash
# 1. Check out a previous commit and re-run the deploy
git checkout <previous-commit>
./infra/07-deploy.sh
git checkout main

# 2. Manually pull a specific image tag on EC2
ssh ec2-user@<public-ip>
sudo systemctl stop role-tracker
docker pull 941894778585.dkr.ecr.ca-central-1.amazonaws.com/role-tracker:<sha>
# (then edit /etc/systemd/system/role-tracker.service to use that tag, or
#  just docker run it manually)
```

In practice, since deploys are fast (~3-5 min) and you control the source tree, "fix the bug and redeploy forward" is the usual answer.

### CI/CD (alternative to manual deploys)

A GitHub Actions workflow can deploy on every push to `main`. Setup is in [`docs/cicd-setup.md`](cicd-setup.md). Right now the project uses **manual deploys via `./infra/07-deploy.sh`** as the primary path. CI/CD is the optional automation layer.

### Pushing secrets to SSM

Secrets (API keys, tokens, the `APP_TOKENS` JSON, the cap override JSON) live in AWS Systems Manager Parameter Store. Update via the AWS CLI:

```bash
aws ssm put-parameter \
  --name /role-tracker/<NAME> \
  --value '<value>' \
  --type SecureString --overwrite

ssh ec2-user@<public-ip> 'sudo systemctl restart role-tracker'
```

Container reads SSM at startup, so a restart is required.

The script `infra/04-ssm.sh` does an interactive bulk-upload from your `.env` file the first time you set up the project.

---

## 5. User management

The live deployment is a private beta — a small set of allow-listed users, each with their own bearer token. Tokens are minted from your laptop using a Python CLI; the result lands in SSM and the running container picks it up after a restart.

### How auth works

- A single SSM parameter at `/role-tracker/APP_TOKENS` holds a JSON map: `{"<token>": "<user_id>"}`.
- Every API request must include `Authorization: Bearer <token>`.
- The `BearerTokenMiddleware` rejects:
  - missing or malformed header → 401
  - token not in the map → 401
  - the token's bound `user_id` does not match the URL path's `user_id` → 403

So `rafin_`'s token cannot read `smrah`'s data — the middleware enforces it.

### Add a new user

```bash
uv run python infra/users/manage_users.py add <user_id>
```

Prints a 43-character random token. **Save it before closing the terminal** — the script does not store it anywhere readable. Then restart the API container so it loads the new token:

```bash
ssh ec2-user@<public-ip> 'sudo systemctl restart role-tracker'
```

Send the new tester three things over a private channel (DM, encrypted email, password manager share):

1. The URL — `https://roletracker.app`
2. Their `user_id` — e.g. `rafin_`
3. Their token

They paste user_id + token into the LoginPage on first visit.

### Rotate a user's token

If a token leaks (committed to a repo, shown in a screenshot, pasted in a chat):

```bash
uv run python infra/users/manage_users.py rotate <user_id>
ssh ec2-user@<public-ip> 'sudo systemctl restart role-tracker'
```

Old token is invalidated immediately on restart; new one is printed. Send the new token to the user.

### Remove a user

```bash
uv run python infra/users/manage_users.py remove <user_id>
ssh ec2-user@<public-ip> 'sudo systemctl restart role-tracker'
```

The token is revoked. **The user's S3 / DynamoDB data is preserved** — intentional, so audit context stays. If you need a hard purge (right-to-delete, etc.), do it manually through the AWS console.

### List existing users

```bash
uv run python infra/users/manage_users.py list
```

Prints `user_id` + a 12-char token prefix (so you can tell users apart in logs without seeing the full secret).

---

## 6. Caps, costs, and quotas

There are two kinds of cost limits in the system: a **per-user daily $/cap** (enforced server-side, returns 429 when exceeded) and a **JSearch monthly request quota** (tracked, surfaced in the UI, not enforced).

### Daily cost cap

Every Anthropic / OpenAI feature has an estimated cost (`FEATURE_COST_USD` in `src/role_tracker/usage/store.py`). Before each LLM call, `enforce_daily_cap` adds the call's cost to the user's spend so far today; if it would exceed the cap, the route returns **429** with a "resets at 00:00 UTC" message.

The cap is read from environment variables (set via SSM in prod):

| Variable | Default | What it does |
|---|---|---|
| `DAILY_COST_CAP_USD` | `1.50` | Global cap. Applied to every user with no override. |
| `DAILY_COST_CAP_USD_OVERRIDES` | empty | JSON map `{"<user_id>": <cap>}`. Listed users get the override. |

So a typical prod setup: friend testers at the global $1.50; admin at $10.

#### Raise the global cap

```bash
aws ssm put-parameter \
  --name /role-tracker/DAILY_COST_CAP_USD \
  --value "3.00" --type String --overwrite

ssh ec2-user@<public-ip> 'sudo systemctl restart role-tracker'
```

#### Set per-user overrides

```bash
aws ssm put-parameter \
  --name /role-tracker/DAILY_COST_CAP_USD_OVERRIDES \
  --value '{"smrah":10.00}' \
  --type SecureString --overwrite

ssh ec2-user@<public-ip> 'sudo systemctl restart role-tracker'
```

Empty / unset = no overrides; everyone gets the global.

### Inspect today's spend

```bash
# What's in SSM right now
aws ssm get-parameter --name /role-tracker/DAILY_COST_CAP_USD \
  --query Parameter.Value --output text 2>/dev/null || echo "unset (default 1.50)"

aws ssm get-parameter --name /role-tracker/DAILY_COST_CAP_USD_OVERRIDES \
  --with-decryption --query Parameter.Value --output text 2>/dev/null || echo "no overrides"

# What a specific user has spent today (via the live API)
curl -H "Authorization: Bearer <smrah-token>" \
  https://roletracker.app/api/users/smrah/usage
```

The `/usage` endpoint returns a JSON dump of feature counts + estimated costs for the current month.

### JSearch quota

The free RapidAPI plan allows **200 requests/month**. Each pipeline run costs 2 × number of saved queries. The `usage` endpoint surfaces a JSearch quota progress bar.

There is **no automatic block** if you'd exceed the quota — the request just fails at the JSearch side with a 429. If you're close to the limit, the user-facing dashboard nudges you to wait until next month.

---

## 7. Operations cookbook

Common tasks and what to do when things break.

### Find the EC2 public IP

```bash
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=role-tracker-app" \
            "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text
```

### Watch live logs

```bash
ssh ec2-user@<public-ip> 'sudo journalctl -u role-tracker -f'
```

Ctrl-C to exit. This shows uvicorn output, every HTTP request, every error.

### Last 100 log lines (no follow)

```bash
ssh ec2-user@<public-ip> 'docker logs role-tracker --tail 100'
```

### Container status + image SHA

```bash
ssh ec2-user@<public-ip> 'sudo systemctl status role-tracker'
ssh ec2-user@<public-ip> 'docker inspect role-tracker --format "{{.Config.Image}}"'
```

### Restart the container without redeploying

```bash
ssh ec2-user@<public-ip> 'sudo systemctl restart role-tracker'
```

Triggers: docker stop → docker pull `:latest` → docker run.

### Force redeploy without a code change

```bash
./infra/07-deploy.sh
```

Always rebuilds + pushes. If you just need the EC2 instance to re-pull the same `:latest`, use the restart command above.

### "I changed Wi-Fi networks and SSH stopped working"

Your public IP changed and the EC2 security group rejects you on port 22. Re-run [`infra/06-ec2.sh`](../infra/06-ec2.sh) — it adds your current IP to the security group. The old rule stays in place; clean up old IPs in the EC2 console manually if you want a tidy SG.

### "The deploy script hangs / times out"

Most common cause: Docker Desktop isn't running on your laptop. Open it, wait for the whale icon to settle, re-run.

Second most common: SSH host-key change after EC2 reboot. The script uses `StrictHostKeyChecking=accept-new` so first connect is auto-trusted, but subsequent connects enforce it. If the host key changed:

```bash
ssh-keygen -R <public-ip>
# next ssh will accept the new key
```

### "User reports: the page won't load"

Three checks in order:

1. Is the container running? `sudo systemctl status role-tracker` should show `active (running)`.
2. Is the API responding? `curl https://roletracker.app/api/health` should return `{"status":"ok"}`.
3. Is Cloudflare DNS resolving? `dig roletracker.app` should return Cloudflare IPs.

If 1 fails: `sudo systemctl restart role-tracker` and check logs. If 2 fails but 1 succeeds: Cloudflare/origin SSL config issue. If 3 fails: DNS is broken (unusual; Cloudflare dashboard).

### "User reports: I get 401"

Their token isn't recognised. Most likely:

- Token was rotated and they have the old one — rotate again, send fresh.
- They didn't actually paste the token (or pasted with extra whitespace) — have them re-enter on the LoginPage.
- The container hasn't been restarted since the SSM map was updated — `sudo systemctl restart role-tracker`.

### "User reports: I get 403 trying to reach my own jobs"

The `user_id` in the URL doesn't match the token's bound user_id. The frontend builds URLs from `localStorage.user_id`, so this is almost always an out-of-sync localStorage. Have them clear localStorage and sign in again.

### "User reports: I get 429 Daily cost cap reached"

Working as designed — they spent the configured cap of estimated Anthropic/OpenAI cost in one UTC day. The bucket resets at midnight UTC.

If you want to bump their cap, see [§6 caps](#6-caps-costs-and-quotas).

### "The agent generated a weird letter"

You can't replay the run, but you *can* see what the agent decided:

- Saved letter has a `strategy` field (primary project, narrative angle, fit assessment) and a `critique` field (rubric scores).
- These are visible in the UI's StrategyPanel + CritiquePanel on the job detail page.

If the strategy is wrong (e.g. picked a project that doesn't fit the JD), use the Generate dialog with an instruction like "lead with the X project instead, the agent picked Y last time and it doesn't fit." Or click Regenerate (the dialog handles that too via the radio toggle).

### Bumping a Python or npm dependency

Backend:
```bash
uv add anthropic@latest
uv run pytest -q
git commit -am "chore: bump anthropic"
git push
./infra/07-deploy.sh
```

Frontend:
```bash
cd frontend
npm update
npm run build
git commit -am "chore: npm update"
git push
./infra/07-deploy.sh
```

### Tearing down the AWS stack

If you ever want to walk away from the AWS bill:

```bash
# Stop EC2 charges immediately
aws ec2 terminate-instances --instance-ids <id>

# Delete the rest (idempotent)
aws ecr delete-repository --repository-name role-tracker --force
aws s3 rb s3://role-tracker-data-<acct> --force
for t in applied letters usage queries seen-jobs; do
  aws dynamodb delete-table --table-name role-tracker-$t
done
```

DynamoDB and S3 are free at this scale — only EC2 has a non-trivial monthly cost after the free tier expires (~$10/mo).

---

## 8. Glossary

Project-specific terms you'll see across the code, the docs, and the UI.

| Term | What it means |
|---|---|
| **Agent loop** | The cover-letter writing flow: Claude calls tools (`read_job_description`, `read_resume_section`, `commit_to_strategy`, `critique_draft`, `save_letter`) in a loop until it produces an approved letter. Source: [`src/role_tracker/cover_letter/agent.py`](../src/role_tracker/cover_letter/agent.py). |
| **Cap** | Per-user daily limit on estimated Anthropic + OpenAI cost. Default $1.50/day; override per user via `DAILY_COST_CAP_USD_OVERRIDES`. |
| **Critique** | Haiku-powered scoring of a generated letter against a 100-point rubric. The agent revises if any category fails its threshold. |
| **Extended thinking** | An Anthropic option where the model thinks through a problem before producing an answer. Higher quality on complex tasks; ~3× cost. Toggleable per generate call. |
| **JD** | Job description. The full text of a job posting, fetched from JSearch and stored in DynamoDB. |
| **JSearch** | A RapidAPI service that wraps Google for Jobs. Returns full JD text (unlike most aggregators which truncate). Free tier = 200 requests/month. |
| **Letter version** | One saved cover letter for a (user, job) pair. Each generation, refine, or manual edit creates a new numbered version. Letter v1, v2, v3 all live in DynamoDB and are downloadable as Markdown / PDF / DOCX. |
| **Refine** | Take an existing letter version + free-text feedback; produce a new version that preserves the committed strategy. Different from regenerate. |
| **Regenerate** | Throw away the existing strategy and produce a fresh letter from scratch. Often a different primary project, different angle. |
| **Seen jobs** | The cached list of jobs the system has fetched + ranked for a user. Stored in `role-tracker-seen-jobs` DynamoDB table. The job-list UI reads from here. |
| **Strategy** | The agent's chosen "spine" for a letter: primary project, optional secondary project, narrative angle, fit assessment (HIGH / MEDIUM / LOW). Committed as a tool call before drafting. Saved alongside the letter for later inspection. |
| **Style template** | An optional letter the user pastes into the Generate dialog. The agent mirrors its voice and structure but uses only facts from the actual resume + JD. |
| **Tool call** | An LLM-invoked function call. Anthropic's API supports defining tools (typed function signatures); the model decides when to call them. Our agent has 5 tools — see "agent loop" above. |
| **user_id** | Stable string identifier for a user, used as the partition key on every DynamoDB table and the S3 prefix. Examples: `smrah`, `rafin_`, `ahasan_`. Never PII. |

---

## 9. Where to read deeper

- **API contract** → [`docs/api_spec.md`](api_spec.md) — every HTTP endpoint, request / response schema, status codes.
- **Multi-user details** → [`docs/multi_user.md`](multi_user.md) — the auth model + cap config, with rationale.
- **CI/CD setup** → [`docs/cicd-setup.md`](cicd-setup.md) — GitHub Actions, OIDC, when push-to-main triggers a deploy.
- **Docker walkthrough** → [`docs/docker-setup.md`](docker-setup.md) — what's in the Dockerfile, how the multi-stage build works.
- **First-time AWS setup** → [`docs/aws-onboarding.md`](aws-onboarding.md) — sign-up, CLI auth, SSH keys.
- **AWS deployment plan (historical)** → [`docs/aws-deployment-plan.md`](aws-deployment-plan.md) — original plan, captures the why.
- **Project state snapshot** → [`docs/project_state.md`](project_state.md) — current state, what shipped recently, open work.
- **Agent tutorial** → [`docs/agentic_ai_tutorial.md`](agentic_ai_tutorial.md) — conceptual model of the cover-letter agent. Beginner-friendly.

### Historical plans (snapshots, not living docs)

These describe decisions made at a point in time. Useful for "why did we build it this way" but they don't represent current state:

- [`docs/PLAN.md`](PLAN.md) — original phase plan
- [`docs/phase5_web_app_plan.md`](phase5_web_app_plan.md) — Phase 5 (web app) plan
- [`docs/plan_search_first_home.md`](plan_search_first_home.md) — search-first home page
- [`docs/cover-letter-interactive-plan.md`](cover-letter-interactive-plan.md) — superseded card-flow plan
- [`docs/cover_letter_dialog_plan.md`](cover_letter_dialog_plan.md) — current cover-letter flow (status: shipped)
- [`docs/demo_prep.md`](demo_prep.md) — demo notes
