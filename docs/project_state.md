# Role Tracker — Project State

> A **snapshot** of where the project is right now: what's shipped, what's
> running in production, what's open. For "how do I do X" the operator
> entry point is [`docs/HANDBOOK.md`](HANDBOOK.md). This file is the
> "what is this and how did it get here" companion.
>
> **Last updated:** 2026-05-08
> **Current branch:** `main`
> **Repo:** github.com/smrahman0009/role-tracker-ai
> **Live URL:** https://roletracker.app

---

## 1. One-line summary

A live, multi-user job-search assistant: ranked job listings against a
user's resume + an LLM-agent-driven cover-letter writer with an
interactive Generate dialog. Live on AWS, behind Cloudflare TLS, gated
by per-user bearer tokens, with daily cost caps.

---

## 2. Where we are today

### Live production

- **URL:** https://roletracker.app — Cloudflare DNS + Flexible SSL fronting
  an AWS EC2 t2.micro running the Docker image.
- **Stack:** FastAPI + React, packaged into one image, served by Uvicorn
  on EC2. AWS-native storage (DynamoDB + S3), secrets in SSM Parameter
  Store.
- **Region:** `ca-central-1`.
- **Cost profile:** ≈ $0/month (free tier) for now; ~$10/month after the
  EC2 free tier expires in year 2. Anthropic / OpenAI usage is the
  variable cost — bounded by the daily cost cap.

### Active users (private beta)

| user_id | Role | Status |
|---|---|---|
| `smrah` | Admin / power user | Active |
| `rafin_` | Friend tester | Active (token rotated 2026-05-08) |
| `ahasan_` | Friend tester | Active (token rotated 2026-05-08) |

### Daily cost cap

- Global default: **$1.50/day** per user, resets at midnight UTC.
- Per-user override: configurable via `DAILY_COST_CAP_USD_OVERRIDES`
  env var (JSON map). Used to give the admin headroom while testing.
- Currently neither the global nor the override is set in SSM, so the
  code default ($1.50) applies to all three users.

### Ops surface

- **Deploy:** `./infra/07-deploy.sh` (manual, ~3-5 min).
- **Token mgmt:** `uv run python infra/users/manage_users.py {add,rotate,remove,list}`.
- **Logs:** `ssh ec2-user@<ip> 'sudo journalctl -u role-tracker -f'`.
- **Health:** https://roletracker.app/api/health.

---

## 3. What shipped recently

In rough chronological order, most recent first.

### 2026-05-08 — Cover-letter Generate dialog ✅
A single Generate button on the letter workspace opens a dialog where
the user can:
- Type an optional steering instruction ("make it punchy, mention my
  fintech work").
- Paste an optional style template (an existing letter to mirror in
  voice and structure).
- Toggle Anthropic's extended-thinking mode (~3× cost, better quality
  on tricky JDs).
- Pick "Start from scratch" or "Edit current draft (vN)" via a radio
  toggle — the same dialog handles both /generate and /refine.

Replaces the per-paragraph "card" flow that lived in
`CoverLetterAnalysisPanel` + `CoverLetterDraftPanel`. Those components,
their hooks, the `/cover-letter/{analysis,draft,finalize}` routes, the
related Pydantic schemas, and their tests were all deleted.

The standalone Regenerate and Refine buttons were also removed — the
new dialog covers both with its mode toggle.

Plus polish that came with this:
- Live progress phase labels during generation ("Reading the job
  description…", "Critiquing the draft…", "Saving the letter…") —
  rendered under the spinner.
- ATS-friendly URL rendering in the contact header (plain
  `https://linkedin.com/...` instead of `[LinkedIn](url)` markdown
  syntax — many ATS scrapers strip markdown links and lose the URL).
- Off-topic deflection paragraph in the agent's system prompt.
- Per-user daily-cost-cap override
  (`DAILY_COST_CAP_USD_OVERRIDES` env var).

Plan: [`docs/cover_letter_dialog_plan.md`](cover_letter_dialog_plan.md).

### 2026-05-07 — Multi-user beta (MU-1 through MU-5) ✅
- **MU-1:** Multi-token bearer-token middleware. Each token is bound to
  one user_id; cross-user paths return 403.
- **MU-2:** Per-user daily cost cap with midnight-UTC reset.
- **MU-3:** CLI for token management (add / rotate / remove / list)
  in [`infra/users/manage_users.py`](../infra/users/manage_users.py).
- **MU-4:** Cloudflare DNS + HTTPS in front of the EC2 instance.
- **MU-5:** Ops doc, README refresh, and live deploy verified.

Onboarded `smrah` first, then `rafin_` and `ahasan_` as friend testers.

### Earlier — Cover-letter chat exploration (abandoned)
Spent time prototyping a chat-based cover-letter UI with conversation
persistence + SSE streaming on `feat/cover-letter-chat`. Determined the
chat surface was overkill for this scope (cover letters are one-shot
documents, not interactive sessions). Replaced with the simpler dialog
approach above. Branch left in git history; not merged.

### Earlier — Phase 5/6 web app, multi-user backend, cloud-native deploy
Work spanning ~3 weeks before this session. Listed for completeness:
- FastAPI backend with 30+ routes
- React 19 frontend (Vite, TanStack Query, Tailwind v4)
- DynamoDB + S3 + SSM cloud-native storage layer
- AWS EC2 deployment with manual deploy script
- Resume upload, job ranking, agentic cover-letter generator
- Refine + Polish + Why-Interested LLM features
- Application tracker, usage dashboard
- Cover-letter version history (Markdown / PDF / DOCX downloads)

---

## 4. What's open

### Phase 4 — real-job prompt iteration
Run the new Generate dialog against several real job postings and tune
the agent's system prompt where outputs feel weak. Only meaningful with
real Anthropic calls and real JDs. Currently deferred — pending the
admin actually using the live deployment for cover letters.

### Public demo mode
A read-only `user_id=demo` with seeded sample data so a recruiter / link
visitor can click through the app without a token. Highest-leverage
"polish" item for portfolio impact. Not started.

### Cloudflare Access (security hardening)
Zero-trust gateway in front of the site so unauthorised visitors don't
even see the login page. Free tier covers 50 users. Defensible deferral
at 3 testers. Discussed and parked.

### Daily refresh job
Optional EventBridge rule that re-runs the matching pipeline overnight
so the user wakes up to fresh ranked jobs. Defensible deferral —
on-demand refresh from the UI works fine.

---

## 5. Architecture in one diagram

For the full architecture explanation, see
[`docs/HANDBOOK.md` §2](HANDBOOK.md#2-architecture-overview). One-paragraph
version:

```
Browser  →  Cloudflare DNS (TLS)  →  AWS EC2 (Docker container)
                                       │
                                       ├──→  AWS DynamoDB  (5 tables, all PK=user_id)
                                       ├──→  AWS S3        (resume PDFs)
                                       ├──→  AWS SSM       (secrets + token map + cap overrides)
                                       ├──→  Anthropic API (cover-letter agent + refine + polish)
                                       ├──→  OpenAI API    (job-resume embedding for ranking)
                                       └──→  JSearch API   (Google for Jobs wrapper, fetches JDs)
```

### What's notable about the design

- **Storage is abstracted behind `Protocol` interfaces.** Same call sites
  work against JSON-on-disk (dev, `STORAGE_BACKEND=file`) or DynamoDB +
  S3 (prod, `STORAGE_BACKEND=aws`).
- **Per-user data isolation is enforced at the middleware layer.** Bearer
  token → user_id mapping rejects URL paths with mismatched user_ids.
- **Cost guardrails are server-side.** Every Anthropic / OpenAI feature
  has an estimated cost; daily spend is summed in DynamoDB; routes
  return 429 when the configured cap would be exceeded.
- **The cover-letter agent is structurally grounded.** Tools force the
  agent to fetch resume content via `read_resume_section()` before
  claiming anything; a Haiku critic scores against a rubric and forces
  rewrites if categories fail their thresholds.

---

## 6. Known gotchas

Things to be aware of when picking this up cold or onboarding someone:

### The deploy script reads from your local working tree
`./infra/07-deploy.sh` builds an image from whatever branch is checked
out — it does **not** pull from `main` first. Best practice: merge to
`main`, push, then deploy.

### Container reads SSM only at startup
Updating an SSM parameter (token map, cap config, API key) does **not**
take effect until the container restarts:

```bash
ssh ec2-user@<ip> 'sudo systemctl restart role-tracker'
```

This is intentional — startup-time loading is cheaper and simpler than
hot-reload. Just remember to restart.

### Two storage backends, one codebase
`STORAGE_BACKEND=file` is the dev default; `aws` is production. If you
forget to set `aws` in prod, the container will silently use file
storage inside the container's writable layer — data survives restart
but vanishes on container delete (i.e. on every redeploy).

The systemd unit on EC2 explicitly sets `STORAGE_BACKEND=aws`, so this
is fine in practice. But it's worth knowing.

### Tokens that get pasted in chat / commits / screenshots are compromised
The bearer-token entropy (256 bits) makes brute-force impossible, but
plain-text leaks are. Rotate via
`infra/users/manage_users.py rotate <user_id>` + container restart.

### Frontend localStorage holds the user_id
The React SPA reads `user_id` from `localStorage.rt:user_id` and uses it
to build URLs. If a user changes their `user_id` in profile, they need
to clear localStorage and sign in again — the frontend doesn't refresh
the cached value.

### The agent's strategy is committed early and won't change mid-letter
Refine preserves the strategy by design; if the user wants a different
primary project, they need to Regenerate (which throws the strategy
away). The Generate dialog's radio toggle makes this explicit.

---

## 7. If you're picking this up cold

Read in this order:

1. **[`docs/HANDBOOK.md`](HANDBOOK.md)** — operator entry point. Architecture, deploy, user management, ops. ~30 min skim.
2. **[`docs/agentic_ai_tutorial.md`](agentic_ai_tutorial.md)** — conceptual walkthrough of how the cover-letter agent works. Useful if agent code is new to you.
3. **[`docs/api_spec.md`](api_spec.md)** — only if you're going to touch HTTP routes.
4. **This file (`project_state.md`)** — for context on what's been built and what's next.

Then:

```bash
git clone git@github.com:smrahman0009/role-tracker-ai.git
cd role-tracker-ai
uv sync --all-extras
cp .env.example .env  # fill in API keys
uv run pytest -q      # confirm baseline is green (~485 tests)
uv run uvicorn role_tracker.api.main:app --reload --port 8000
# in another terminal:
cd frontend && npm install && npm run dev
```

Then open http://localhost:5173. Sign in with `user_id=smrah` and an
empty token (dev mode skips auth when `APP_TOKEN`/`APP_TOKENS` are unset).
