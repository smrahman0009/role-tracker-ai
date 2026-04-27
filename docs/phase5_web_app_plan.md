# Phase 5+ — Web App Pivot Plan

> **Status:** planning, not yet started.
> **Created:** 2026-04-27
> **Target branch:** `phase/5-web-app` (long-lived, sub-features merge in)

---

## Why we're pivoting

The original Phase 5 plan was a daily email digest with a Gmail SMTP
integration, plus an Azure Functions timer trigger to run the pipeline
unattended. That plan is being **replaced** with a web app for three
reasons:

1. **Portfolio value.** The user is actively job-hunting and has no
   agentic-AI / LLM project to show recruiters yet. A deployed web app at
   a real URL is a significantly stronger conversation starter than a
   CLI tool.
2. **Quality reality.** Cover-letter quality reaches roughly 90%
   autonomously. The last 10% is honestly best handled by human review
   with the option to refine, not by sending automated emails. A UI that
   surfaces the agent's strategy + critique score and lets the user say
   "make this more technical" or "shorter" turns this into a *useful*
   tool rather than a fully autonomous gamble.
3. **End-to-end story.** Most "AI app" demos in the wild are thin
   chat-wrapper UIs. Ours has a strategy phase, a critique loop with a
   110-point rubric, prompt caching, and deterministic safety checks
   — all preserved and now exposed through a clean API. That's a real
   differentiator at recruiter scale.

---

## What success looks like

A deployable URL the user can put on a resume / send to recruiters where:

1. **They log in** (single-user for now, hard-coded auth; designed to be
   swapped for real auth later).
2. **They see ranked job matches** as a list of cards on the home page —
   each card shows title, company, location, salary, publisher, fit
   assessment, match score, and a one-line JD preview. No full JD on
   this page (it would overwhelm the layout).
3. **They click "View details"** on a card and land on a dedicated job
   detail page (`/jobs/:job_id`). This page shows the full JD, has the
   "Generate cover letter" button, and is where the rest of the per-job
   work happens. **One page, one URL, one job application.**
4. **They click "Generate"** on the job detail page → progress indicator
   → letter appears inline below the JD, alongside the agent's strategy
   (primary project, narrative angle, fit) and the critique score
   breakdown.
5. **They can refine** with free-text feedback ("make it more technical",
   "shorter", "lead with the audio ML work") → agent revises in place,
   preserving the original strategy and grounding.
6. **They can download** as Markdown or PDF, or **mark as applied** so
   the job moves to a "Applied" filter and doesn't clutter the main list.
7. **Letter version history** is preserved per job so they can compare
   drafts within the same detail page.

**Realistic timeline:** 30-50 hours of work across 6-10 sessions.

---

## Tech stack decisions (locked in)

| Layer | Choice | Why |
|---|---|---|
| Backend framework | **FastAPI** | Already use Pydantic; async support; auto-generated OpenAPI docs are a portfolio plus |
| Frontend framework | **React + Vite** | Recruiter-recognised; Vite for fast dev |
| Styling | **Tailwind + shadcn/ui** | Modern, clean, looks polished without hand-designing |
| Backend hosting | **Azure App Service F1 (free tier)** | Always free; one-click upgrade to B1 when needed |
| Frontend hosting | **Azure Static Web Apps (free tier)** | Always free; built-in custom domain + SSL |
| File storage | **Azure Blob Storage** | Cheap (~$0.05/month for our scale); resumes + letters |
| Database | **Cosmos DB free tier** | Always free 1000 RU/s + 25GB; document model fits letter metadata + version history |
| Secrets | **Azure Key Vault** | Free for 10K ops/month |
| Observability | **Azure Application Insights** | First 5GB/month free |
| Auth (Phase 5-7) | Hardcoded user_id in API + minimal placeholder login | Single-user mode |
| Auth (deferred) | Auth0 or Clerk or Azure AD B2C | Real auth dropped in when going multi-user |

**Realistic monthly cost at single-user scale: under $2/month.**

---

## Azure free-tier strategy

App Service F1 free tier specifics:

- 1 GB RAM, 1 GB storage
- 60 minutes of CPU compute per day
- HTTPS via `*.azurewebsites.net` (no custom domain in F1; use Static Web
  App's domain instead)
- Sleeps after 20 minutes idle (~30 second cold start)

**Capacity check:** a letter takes ~30-60s to generate. 60 minutes/day
of compute = roughly 60 letters/day before hitting the cap. For one
user generating 5-10 letters/day, that's 10-20% utilisation. Plenty.

**Upgrade path** if usage grows or always-on is needed:
- App Service F1 → B1 (~$13/month) — single click in Azure portal, no
  code changes. Adds custom domain on backend, no cold starts, more
  compute headroom.
- Static Web Apps free → Standard (~$9/month) — also a single click.

**Avoid the trial-credit trap:** new accounts get $200 free credit for 30
days, but those expire. We will stick to **always-free tier services**
and ignore the trial credit, so nothing lapses into paid status when
day 31 hits.

**Spending guardrail:** set a $5/month budget alert in Azure Cost
Management before deploying anything. Cheap insurance against accidental
provisioning.

---

## Architectural principles

### 1. The existing pipeline is the engine; the web layer is the consumer

Everything in `src/role_tracker/` already works as a library. FastAPI
becomes a *second consumer* alongside the existing CLI script. We do
**not** rewrite the agent for the web app; we wrap it.

### 2. Single-user now, multi-user-ready always

Even though there's only one user, every API endpoint takes `user_id`
explicitly. No global current-user state. No hard-coded "smrah"
anywhere outside config. When real auth lands later, we replace the
"give me user_id from a header" middleware with "give me user_id from a
JWT" — and nothing else needs to change.

### 3. Long operations are async with polling

Letter generation takes 30-60 seconds. The API uses a job-id pattern:
- `POST /letters/generate` returns `{job_id: "...", status: "pending"}`
  immediately
- `GET /letters/jobs/{job_id}` returns current status (pending →
  running → done) and the letter when ready
- Frontend polls every 2-3 seconds while running, shows a progress
  indicator

This is simpler than WebSockets and works fine for a single-user app.
Background tasks run inside FastAPI's lifecycle (no separate worker
needed at this scale).

### 4. Strategy + critique are first-class API responses

The agent's committed strategy (primary project, narrative angle, fit
assessment) and final critique score (110-point rubric breakdown) are
returned alongside the letter text. The frontend shows them to the
user — that's the "trust me" story for recruiters: the agent doesn't
just produce text, it explains what it was trying to do and how it
graded itself.

### 5. Storage layout

| Data | Where | Why |
|---|---|---|
| Letter content (Markdown) | Azure Blob Storage | Big-ish, immutable, cheap |
| Strategy + critique | Cosmos DB | Small JSON, queryable |
| Job metadata (id, title, company, applied flag) | Cosmos DB | Queryable, indexed |
| Resume PDFs | Azure Blob Storage | One per user, replaceable |
| Resume embedding cache | Cosmos DB | Small JSON keyed by resume hash |

---

## Phasing

### Phase 5 — FastAPI backend (no frontend)

**Goal:** all the engine behaviour exposed via HTTP. Tested with curl /
Postman. No UI.

**Endpoints (single-user, `user_id` always passed):**

```
POST   /users/{user_id}/resume           upload PDF, replaces existing
GET    /users/{user_id}/resume           retrieve current resume metadata

GET    /users/{user_id}/jobs             list ranked jobs (triggers fetch
                                          + match if not cached)
POST   /users/{user_id}/jobs/refresh     force re-fetch from JSearch
GET    /users/{user_id}/jobs/{job_id}    job detail + match score

POST   /users/{user_id}/jobs/{job_id}/letters         generate letter
                                                       returns job_id (async)
GET    /users/{user_id}/letters/jobs/{generation_id}  poll status
GET    /users/{user_id}/jobs/{job_id}/letters         list versions
GET    /users/{user_id}/jobs/{job_id}/letters/{ver}   get specific version
POST   /users/{user_id}/jobs/{job_id}/letters/refine  refine with feedback
                                                       returns new job_id

POST   /users/{user_id}/jobs/{job_id}/applied         mark as applied
DELETE /users/{user_id}/jobs/{job_id}/applied         unmark
```

**Phase 5 also includes:**
- IP allowlist middleware (reads `IP_ALLOWLIST` env var, returns 403 to
  off-list requests; empty value disables the check for local dev).
- Rate-limiting middleware: 20 cover-letter generations per user per day.

**Out of scope for Phase 5:** real auth, frontend, deployment.

### Phase 6 — React frontend (local development)

**Goal:** clean minimal UI consuming the local FastAPI backend.

**Pages (3 total — keep it simple):**

1. **Login** (`/login`) — placeholder; sets `user_id` in localStorage.
2. **Job list** (`/`) — cards of ranked matches showing title, company,
   location, salary, publisher, fit badge, match score, 1-line JD
   preview, and "View details" link. Filter tabs: All | Unapplied | Applied.
3. **Job detail** (`/jobs/:job_id`) — combined view that contains
   everything for one application:
   - Header: title, company, fit assessment, match score, salary, URL,
     [Mark applied] button.
   - Full JD (collapsible after first read).
   - "Generate cover letter" button (when no letter exists yet).
   - Letter viewer (when letter exists): Markdown rendering inline.
   - Strategy panel: primary project, narrative angle, fit reasoning.
   - Critique scorecard: 110-point breakdown.
   - "Refine with feedback" textarea + button.
   - Version history dropdown to switch between drafts.
   - [Download Markdown] [Download PDF] buttons.

   One URL per job application = simpler routing, no jumping between
   pages, easier mental model.

**Out of scope for Phase 6:** deployment, real auth.

### Phase 7 — Interactive refinement

**Goal:** the "make it more technical / shorter" feature actually works
without breaking grounding or the strategy.

**Approach:** new agent flow `refine_with_feedback(prev_letter, feedback,
strategy)`. Agent receives the previous letter + the user's free-text
feedback + the original committed strategy. It cannot change the
strategy. It can only revise the letter to address the feedback while
maintaining the critique-rubric thresholds.

This is non-trivial — it's a new agent flow, not just a parameter on
the existing one.

### Phase 8 — Azure deployment

**Goal:** real URL the user can share.

- Frontend → Static Web Apps free tier
- Backend → App Service F1 free tier
- Resumes + letters → Blob Storage
- Metadata → Cosmos DB free tier
- Secrets → Key Vault
- CI/CD → GitHub Actions deploying on merge to main

### Phase 9 — Portfolio polish

- Loading states (skeleton screens, spinners with progress messages)
- Error handling (user-facing error toasts)
- Mobile responsive
- README with screenshots
- Demo video (~90 seconds)
- Custom domain (optional, ~$12/year)
- Open-source licence + contributing notes (optional)

---

## Locked decisions (resolved 2026-04-27)

All architectural questions raised during planning have been resolved:

1. **Resume model.** One resume per user. Multiple resumes deferred.

2. **Letter version cap.** Keep all versions until the user marks the
   job as applied; after that, keep the final version only.

3. **Auth approach.** Hardcoded `user_id` for Phases 5-8. Real auth
   choice (Auth0 / Clerk / Azure AD B2C) deferred until multi-user.
   Plus: **IP allowlist as basic access control** — see decision 8.

4. **Rate limiting.** 20 cover-letter generations per day per user,
   enforced at the FastAPI middleware layer.

5. **Frontend state management.** React `useState` / `useReducer` for
   component-local state plus **TanStack Query** for all API-backed
   state (job list, letters, poll status). No global store library
   yet. If global state is needed later, **Zustand** drops in with
   minimal migration cost.

6. **Pipeline triggering.** Cache the ranked-jobs result; refresh from
   JSearch only via an explicit "Refresh jobs" button in the UI.

7. **PDF download.** Server-side rendering (FastAPI returns PDF) for
   stable shareable URLs.

8. **IP allowlist (new requirement).** A `IP_ALLOWLIST` environment
   variable holds a comma-separated list of allowed IPs. FastAPI
   middleware checks each request's source IP (via `X-Forwarded-For`
   when behind Azure App Service) against the allowlist; returns 403
   to anyone outside it. Empty `IP_ALLOWLIST` disables the check
   (useful for local dev). Cheap, effective single-user defence.

9. **MVP cut = Phase 9 (polished).** The recruiter-ready demo is the
   *polished* version, not a rough Phase 8 deployment. Implication:
   no shareable URL until Phase 9 ships. Total path-to-resume timeline
   stays at 30-50 hours.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Scope creep — turning a simple app into a complex one | Hard stop at end of each phase; merge before starting next |
| Letter quality regresses during refactor | Re-run the Shopify + McKesson smoke tests after each major change |
| Azure costs surprise the user | $5/month budget alert before any provisioning; stick to always-free tiers only |
| Cold-start latency on F1 backend frustrates the user | Acceptable for portfolio demo; B1 upgrade is one click if needed |
| Single-user assumption hard-codes things that should be parameterised | Code review every endpoint for hard-coded `user_id` before merging Phase 5 |
| The refine-with-feedback agent breaks grounding | Critique runs on every refinement output, same hallucination threshold |

---

## Pre-coding artefacts (resolved 2026-04-27)

Both pre-coding artefacts are confirmed required before any FastAPI or
React code is written:

1. **OpenAPI spec / endpoint table** committed to `docs/api_spec.md`
   as the first Phase 5 deliverable. User reviews + approves the
   shape before any FastAPI code lands.

2. **Frontend wireframe** committed to `docs/wireframes/` as the first
   Phase 6 deliverable. **Tool: Excalidraw** — its `.excalidraw` files
   are JSON, editable, openable at excalidraw.com, and can be committed
   to the repo so the wireframe evolves alongside the code.

3. **MVP cut: Phase 9 (polished).** No partial-demo cut at Phase 8.
