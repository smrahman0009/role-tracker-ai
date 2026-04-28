# Role Tracker — Project State

> A self-contained handoff document. Written so a future Claude Code session
> (or any collaborator) can read this once and fully understand where the
> project stands, how it got here, and where it's going.
>
> **Last updated:** 2026-04-27 (after Phase 4 merge + architectural rebuild)
> **Current branch:** `main`
> **Repo:** github.com/smrahman0009/role-tracker-ai
>
> **Major direction change (2026-04-27):** The original Phase 5 plan (email
> digest + Azure timer trigger for daily runs) has been replaced with a
> **web-app pivot**. See [phase5_web_app_plan.md](phase5_web_app_plan.md) for
> the detailed plan. Reasoning summarised in §5 below.

---

## 1. Core purpose and functionality

Role Tracker is a **daily, automated job-matching + tailored cover-letter
pipeline** built for personal use by a job-seeking data scientist / ML
engineer in Canada, with planned expansion to 4–5 friends.

The goal is to **replace the human effort of "search job boards → filter
noise → write a letter for each one"** with a single command that does all
three, end-to-end, with ranked results and per-job tailored letters saved
to disk for review.

### What the pipeline does today

```
python scripts/run_match.py --user smrah --limit 30 --top-n 5 --generate-letters
```

This one command:

1. Loads the user profile from `users/smrah.yaml` (resume path, queries,
   exclusion rules, contact info).
2. Parses the PDF resume → raw text.
3. Embeds the resume with OpenAI `text-embedding-3-small` (cached on disk;
   only re-embeds when the text hash changes).
4. Calls the **JSearch API** (RapidAPI, wraps Google for Jobs) with each of
   the user's saved queries; fetches up to `--limit` jobs per query. Server-side
   filters out publishers the user has chosen to hide from their results,
   via JSearch's `exclude_job_publishers` parameter. The default list is
   editable in Settings; it reflects personal filtering preferences only.
5. Deduplicates by `(title, company)`, applies local exclusion filters
   (company, title keyword, publisher — belt-and-suspenders).
6. Embeds each job description, computes cosine similarity against the
   resume vector, ranks by score, takes top-N.
7. Prints the ranked matches with publisher, salary, URL, and full
   (non-truncated) descriptions.
8. **(Phase 4)** For each top-N job, runs an **agentic cover-letter writer**
   that:
   - Calls Claude Sonnet 4.6 in a loop with three tools:
     `read_job_description`, `read_resume_section(topic)`, `save_letter(text)`.
   - After drafting, calls `critique_draft` which invokes Claude Haiku 4.5
     against a 100-point rubric (Hallucination / Tailoring / Voice / Banned
     Phrases / Structure / Gap Handling / Opening-Closing) and returns JSON
     with verdict + priority fixes.
   - Revises up to 2 times if the critique demands it, then saves.
9. Saves each letter to a dated folder alongside its JD snapshot and a
   snapshot of the resume used:

```
data/cover_letters/smrah/
└── 2026-04-22_shopify_staff-machine-learning-engineer_abc123/
    ├── cover_letter.md
    ├── job_description.md
    └── resume_snapshot.txt
```

### Design principle

**Every output you'd want to review later is saved next to its inputs.**
You open one folder and see the letter, the JD that drove it, and the
resume that grounded it. No hunting. No stale outputs from old resume
versions.

---

## 2. Technology stack and tools

### Core language + runtime
- **Python 3.12** (pinned in `pyproject.toml`)
- **uv** for dependency management + virtualenv + script running
  (not pip + venv)

### External services
- **OpenAI API** — `text-embedding-3-small` for resume + job embeddings.
  Cached locally; negligible cost (~$0.001 per full run).
- **Anthropic API** — `claude-sonnet-4-6` for the main cover-letter agent,
  `claude-haiku-4-5-20251001` for the critique scorer. Pay-as-you-go,
  separate from the Claude Max chat subscription.
- **RapidAPI / JSearch** — wraps Google for Jobs. Returns full
  (non-truncated) job descriptions. Free tier = 200 requests/month,
  sufficient for daily use.

### Python dependencies (from `pyproject.toml`)
```
pydantic>=2.0              # data models
pydantic-settings>=2.0     # .env → typed Settings
openai>=1.0                # embeddings
anthropic>=0.25            # cover-letter agent + critique
python-dotenv>=1.0         # load .env
httpx>=0.27                # JSearch HTTP client
jinja2>=3.1                # (reserved for Phase 5 email templates)
pyyaml>=6.0                # user profiles + pipeline defaults
pypdf>=4.0                 # resume parsing
```

Dev: `pytest`, `pytest-cov`, `ruff`.

### Config files
- `.env` — API keys (gitignored). Currently holds `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `JSEARCH_RAPIDAPI_KEY`.
- `config.yaml` — pipeline-wide defaults (`country`, `results_per_page`).
- `users/{id}.yaml` — one file per person the pipeline runs for. Contains
  name, contact info, queries, exclusions, exclude_publishers, resume path.

### IDE + AI tooling
- **VS Code** as the primary editor.
- **Claude Code** (this session) as the coding partner — agentic CLI running
  inside the VS Code terminal. Configured with persistent memory under
  `~/.claude/projects/-Users-smrah-Desktop-development-role-tracker-ai/memory/`.

### Target deployment (future)
- **Azure Functions** (timer trigger) for daily scheduled runs.
- **Gmail SMTP** for the email digest (Phase 5 — not yet built).

---

## 3. Features completed so far

Development is phased. Each phase lives on its own branch, merged to `main`
only after a live smoke test passes. Current state:

### Phase 1 — Project scaffold (merged)
- `pyproject.toml`, ruff config, pytest config
- `.env.example`, `.gitignore`
- Directory layout for modular growth

### Phase 2 — Job fetching (merged — originally Adzuna, later replaced)
- CLI skeleton (`argparse`)
- Config loading (pydantic-settings)
- Basic filter logic

### Phase 3 — Resume matching + multi-user + JSearch (merged)
- **Resume parsing** via `pypdf`.
- **Embedding** via OpenAI; hash-based disk cache so the resume is only
  re-embedded when content changes.
- **Cosine-similarity ranking** — ranks all fetched jobs against the resume
  vector.
- **Strategy Pattern for job sources** — `JobSource` Protocol means swapping
  in a new API is a single new file. Adzuna was removed in favour of JSearch
  because Adzuna truncates descriptions, which tanks ranking quality.
- **Multi-user architecture (Scope A)** — `YamlUserProfileStore` reads
  `users/*.yaml`. Designed to be swapped for a DB-backed store in Scope B
  without touching call sites.
- **Exclusion filters** — per-user company / title-keyword / publisher
  filter lists. Publisher filter is enforced server-side (JSearch's
  `exclude_job_publishers` param) and rechecked locally.
- **Default hidden-publisher list** seeded with sources commonly
  preferred to be filtered out; users edit freely in Settings. The
  list is private to each profile and reflects only personal
  filtering preferences.

### Phase 4 — Cover-letter agent (merged to main)
- **Step 1: Naive generator** (`generator.py`). One Sonnet 4.6 call with a
  stuffed prompt. Kept as the baseline for comparison.
- **Step 2: Pipeline integration.** `--generate-letters` flag on
  `run_match.py` (opt-in, off by default).
- **Step 3: Agent loop with tools** (`agent.py` + `tools.py`). Agent fetches
  resume content on demand via `read_resume_section(topic)`, calls
  `read_job_description()`, saves via `save_letter(text)`. Max 25 iterations,
  30 tool calls.
- **Step 4: Haiku critique + revision loop.** `critique_draft(draft)` calls
  Haiku 4.5 with the rubric; returns structured JSON with `verdict` +
  `priority_fixes`. Main agent revises up to twice before saving. Defensive
  JSON parsing with fallback (handles markdown-fenced JSON).
- **Step 5: Prompt caching.** System prompts (main + critique) and tool
  schemas wrapped in `cache_control: ephemeral`. Live-verified 85-92% cache
  hit rate on stable prefix.

### Phase 4 — Architectural rebuild (merged to main on 2026-04-25)
After observing the agent fabricate qualifications and dump multiple
projects into one paragraph (the McKesson failure), the agent was
restructured:
- **Mandatory strategy phase** via new `commit_to_strategy` tool. Agent
  picks ONE primary project as the spine, optional ONE secondary, a
  one-sentence narrative angle, and an honest fit assessment
  (HIGH / MEDIUM / LOW). Cannot save without committing strategy first.
- **Stricter hallucination check.** Hedge phrasings ("familiar with",
  "informally applied", "started ramping up") explicitly count as factual
  claims requiring resume backing. Any unsupported claim → score 0/25 →
  hard threshold failure → forced rewrite.
- **New rubric category: Narrative Coherence (10 pts, hard threshold 7+).**
  Critic verifies the letter actually executes the agent's committed
  strategy. Penalises 3+ project dumps. Total scale grew 100 → 110.
- **Hard deterministic post-save checks.** Word count 280-420, no paragraph
  > 130 words. Save rejects with specific failures; agent gets 2 retries.
- **Title-relevance filter.** Drops jobs whose titles share no keyword with
  the active queries. Fixes the bug where "data scientist" returned
  backend-engineer roles.
- **Strategy + critique persisted alongside each letter** (`strategy.md`
  and `critique.json`) so users can audit *why* a letter looks the way it
  does.

Live validation: same Shopify role that produced the McKesson-style
hallucinated letter now scores **98/110 approved** with one clean primary
project, honest LOW fit assessment, no fabricated claims.

### Testing + quality
- **73 unit tests** across all modules. Mocked Anthropic and JSearch
  clients in tests; no network in `pytest`.
- `ruff check .` clean.
- End-to-end smoke tests run manually at each step against the live APIs
  with real data.

### Documentation
- `docs/agentic_ai_tutorial.md` — self-contained beginner-to-mid-level
  tutorial on agentic AI using this project as the worked example.
- `docs/PLAN.md` — original phase plan.

### Cost profile (measured)
- **Full run for 5 letters**: ~$0.50–0.75 at Sonnet 4.6 + Haiku 4.5 pricing
  with caching. Daily runs for 1 person = ~$15–20/month.

---

## 4. Current challenges / difficulties

### Quality-level
- **Letters still leak rubric violations after the critique loop.** The
  Shopify smoke test showed the critique successfully fixed the banned-phrase
  ("at the intersection of") and paragraph-count issues from Step 3, but
  didn't fully eliminate soft gap-naming ("started ramping up on PyTorch and
  distributed training") — this would lose points on Category 6 of the
  rubric under COLD_APPLICATION context. Future prompt tuning of the
  critique rubric may be needed.
- **Resume is the condensed version**, not a detailed portfolio. Some rich
  material from the reference letter (undergrad IoT irrigation thesis) is
  not in the resume PDF, so the agent can't use it as a bridge. This is a
  content problem, not a code problem — user can enrich the resume when ready.

### Engineering-level
- **No persistent log of what the agent did.** When an agent produces a
  weird letter, there's currently no way to replay its decisions. Step 6
  (next) addresses this with per-letter JSONL traces.
- **No safety cap on repeat jobs.** If the pipeline runs daily, it will
  re-generate letters for jobs that were already processed yesterday,
  wasting API calls. Needs a deduplication layer keyed on `(user, job_id)`.
- **Single-source job fetching.** Only JSearch is wired up right now. The
  Strategy Pattern allows another source to be added cleanly (e.g.
  Greenhouse, Lever, direct scraping), but none is implemented.
- **No CI/CD.** Tests and ruff run locally; no GitHub Actions yet.

### Non-engineering
- **Claude plan optimisation.** User is currently on Claude Max (~$200 CAD/month)
  but API calls are billed separately from the chat plan. Open question
  whether to downgrade to Pro (~$28 CAD/month) + API credits. This is
  unrelated to the codebase but worth noting on the financial picture.

---

## 5. Next steps / planned features

### Direction change (2026-04-27)

The original Phase 5 plan (email digest) and Phase 6 plan (Azure timer
trigger for daily automated runs) have been **replaced** by a
**web-app pivot**. Reasoning:

- The user is actively job-hunting and needs a portfolio piece showing
  end-to-end AI application development (not just a CLI).
- Cover-letter quality reaches ~90% autonomously; the last 10% is best
  handled by a human-in-the-loop review UI rather than fully autonomous
  emailing.
- A deployable web app URL is more valuable for recruiter conversations
  than a CLI tool.
- The existing Python pipeline becomes the **engine**; FastAPI exposes it
  as HTTP endpoints; React provides the UI.

Detailed plan lives in [phase5_web_app_plan.md](phase5_web_app_plan.md).

### Phase 5 — FastAPI backend
Wrap the existing pipeline as HTTP endpoints (list jobs, generate letter,
poll status, refine with feedback, mark applied). No frontend yet.

### Phase 6 — React frontend (local)
Job list, job detail, generate button, letter viewer, feedback input.
Tailwind + shadcn/ui for clean modern look.

### Phase 7 — Interactive refinement
"Refine with feedback" agent flow — user types "make it more technical"
→ agent revises while keeping committed strategy + grounding intact.
Letter version history.

### Phase 8 — Azure deployment
Static Web Apps (frontend), App Service F1 free tier (backend), Blob
Storage (resumes/letters), Cosmos DB free tier (metadata), Key Vault
(secrets). Realistic monthly cost: under $2/month at single-user scale,
upgrade path to ~$13/month available with one click.

### Phase 9 — Portfolio polish
Loading states, error handling, mobile responsive, README with
screenshots, demo video, custom domain.

### Deferred (former Phase 5/6/7+ — may revisit later)

- Email digest with Gmail SMTP — replaced by the web UI's letter inbox.
- Azure Function timer trigger for fully automated runs — superseded by
  on-demand web-app generation.
- Multi-source job aggregation (Greenhouse + Lever alongside JSearch).
- Semantic `read_resume_section` (vector retrieval instead of keyword
  match) — the embedding infrastructure is already there from Phase 3.
- Referral-mode cover letters (rubric supports WARM_INTRO context already;
  just need a way to pass the referrer name).

---

## 6. Advantages and drawbacks of the current approach

### Advantages

- **Separation of concerns is clean.** Job fetching (`jobs/`), embedding +
  ranking (`matching/`), resume handling (`resume/`), users (`users/`),
  cover-letter generation (`cover_letter/`) — each is a module with a
  single job. Tests mirror the layout.
- **Strategy Pattern means vendor lock-in is low.** Swapping Adzuna out for
  JSearch was a single new file + a deletion. Adding Greenhouse later is
  the same pattern.
- **Multi-user architecture is already in place.** One YAML file per user,
  loaded via a `UserProfileStore` protocol. Adding 4–5 friends requires
  zero code changes.
- **Grounding-first agent design.** The agent can only claim things it has
  actually retrieved from the resume via `read_resume_section`. This
  structurally prevents the most common LLM failure (inventing experience).
- **Self-critique loop uses a rubric, not vibes.** The 100-point rubric is
  deterministic: each category has hard thresholds, and the agent has a
  budget of 3 critiques per letter.
- **Prompt caching is wired up.** 85.6% hit rate on the stable prefix means
  cost is sub-linear in iterations.
- **Every output is auditable.** Each letter is saved next to the JD and
  resume snapshot that produced it — so reproducing or reviewing past work
  is trivial.

### Drawbacks / limitations

- **No evaluation harness.** There's no golden set of (resume, job) pairs
  with expected properties ("letter should mention PyTorch", "letter should
  not claim Rust"). Changes to the prompt or agent are currently judged by
  eyeballing one smoke-test letter. Proper eval is an eventual
  mid-term need.
- **Critique is same-model-family as main agent.** Haiku 4.5 is cheaper and
  structurally different from Sonnet 4.6, but both are from Anthropic. A
  truly adversarial critic would be a different vendor (e.g. a Llama or
  GPT judge) to catch blind spots. Low priority.
- **Single resume per user.** No support for multiple resume variants
  (e.g. "ML resume" vs "backend resume" for different query types).
- **No rate limiting on the job-fetch side.** Running with
  `--limit 100` on the JSearch free tier could exhaust the monthly quota.
  No guard rails yet.
- **Folder naming uses last 6 chars of job ID for uniqueness.** This is
  usually fine, but if JSearch returns non-URL-safe IDs, the folder name
  can look ugly (e.g. trailing `AAAA==` from base64 IDs). Cosmetic.
- **No dedupe across runs.** Running the pipeline tomorrow for the same
  queries will generate letters for jobs that already got letters
  yesterday. Planned for Phase 5.
- **No guardrail on API spending.** A bug causing a runaway loop could
  theoretically burn a lot of credits. The 25-iteration cap in the agent
  loop limits per-letter spend to a known ceiling, but there's no
  per-day budget cap.

---

## 7. Claude Code + VS Code integration

Working well. The pattern that has consistently worked across Phases 1–4:

1. User describes a phase goal in natural language in the Claude Code
   terminal inside VS Code.
2. Claude proposes a step-by-step plan; user approves.
3. Claude writes code directly into the repo via the `Edit` / `Write` tools;
   changes are visible in VS Code's editor and `git diff` live.
4. Claude runs `pytest` and `ruff` via the `Bash` tool; failures are fixed
   before moving on.
5. For steps that exercise real APIs (OpenAI / Anthropic / JSearch), a
   small `scripts/prototype_*.py` harness runs the flow end-to-end against
   live services; outputs land in `data/` and get reviewed in VS Code.
6. User approves the commit message Claude proposes; Claude commits and
   pushes.
7. Branch merges happen via `git checkout main && git merge --no-ff` from
   the same Claude session.

### What works particularly well
- **Persistent memory across sessions.** Claude Code's memory files at
  `~/.claude/projects/.../memory/` survive restarts, so the next session
  already knows the project is Role Tracker, the user's role, and
  preferences around plan-first-then-execute.
- **Parallel tool calls.** Reading multiple files + running `pytest` + lint
  in one turn keeps turnaround fast.
- **Structured refusals + approvals.** Claude asks before destructive or
  shared-state actions (push, merge, delete). User explicitly green-lights
  each.

### What occasionally bites
- **pytest invocation.** `uv run pytest` sometimes needs `uv sync
  --all-extras` before dev deps are available after a fresh install. Once
  synced, it's reliable.
- **Large context files.** Reading big PDFs or long conversation histories
  can truncate. Mitigation: use the `pages` param on `Read` for PDFs and
  keep per-phase conversations scoped.
- **Memory drift.** Auto-memory records what was true when written; when
  code changes, the memory can lag. Claude is instructed to verify
  memory-derived claims against current code before acting on them.

### Overall assessment

The Claude Code + VS Code combination is well-suited for this kind of
exploratory + educational build. The project has moved from empty repo to
working agentic AI system over several sessions, with each step testable,
reviewable, and revertible. The user — who started this project as a
beginner to agentic AI — now has a working agent *and* understands why each
piece is there.

---

## Handoff notes for the next Claude Code session

If you're picking this up cold:

1. **Read [phase5_web_app_plan.md](phase5_web_app_plan.md) first** — that's
   the active plan. This file describes what's been built; that file
   describes what's being built next.
2. **Read [agentic_ai_tutorial.md](agentic_ai_tutorial.md)** for the
   conceptual model of the agent — it was written for this exact project.
3. **Check the current branch** (`git branch --show-current`). `main`
   should hold all merged Phase 1-4 work. New work happens on
   `phase/5-web-app` (branch to be cut when implementation starts).
4. **Run the tests** (`uv run pytest -q`) to confirm the baseline is green
   before making changes. Should be 82/82.
5. **The user's workflow preference** (stored in memory) is: plan first,
   approve, then execute. Propose before coding. Incremental, not
   scaffold-first.
6. **API keys live in `.env`** — never commit that file. Already in
   `.gitignore`. The `.env.example` template lists required keys.
7. **The user's resume is `data/resumes/smrah.pdf`.** It's the condensed
   version. When assessing letter quality, the agent can only ground
   claims in what's actually in that PDF.
8. **Architectural rebuild context.** The cover-letter agent has a
   mandatory `commit_to_strategy → critique → save` flow. Don't bypass it
   when wrapping in HTTP endpoints; instead, expose the strategy and
   critique results as part of the API response so the frontend can
   display them.

You're in good shape to continue. Good luck.
