# Plan: search-first home page

Replace the cached Job List with an ad-hoc search form on `/`. Resume +
What/Where + optional filters → live JSearch query → ranked results
below. Settings keeps the recurring pieces (profile, daily auto-search,
hidden lists).

## Why

The current home page filters a cached snapshot. Locations and types
not in the cache (e.g., Halifax) can't be surfaced — filters narrow,
they can't broaden. A search-first page makes the resume + query the
explicit inputs and removes the "why isn't X in the dropdown" trap.

## Resolutions to the 9 plot holes

| # | Plot hole | Resolution |
|---|---|---|
| 1 | Daily refresh and ad-hoc share one snapshot, so each clobbers the other | Add a `seen_jobs` store keyed by `job_id`. Both writers append to it. The "current view" is just a list of IDs. |
| 2 | Detail page 404s after the snapshot rotates | Detail + letter routes read from `seen_jobs`, not from the current snapshot. |
| 3 | What does the user see on return visits? | Last ad-hoc results, with a timestamp and a "New search" button. Form is pre-filled with the last spec. |
| 4 | Saved searches feel dead in an ad-hoc world | Reframe as **"Daily auto-search"**. Add a "Save as daily" affordance on the ad-hoc form so users discover it. |
| 5 | JSearch quota burn (free tier ≈ 200 req/mo) | Ad-hoc uses `limit_per_query=20` (10 cost units/search ≈ 40 searches/mo). Daily refresh keeps `limit_per_query=50`. |
| 6 | Resume gate | Search button disabled and form dimmed until a resume exists. |
| 7 | Sync vs async search (30–60s pipeline) | Async, mirroring the refresh pattern. POST returns 202 + `search_id`; client polls. |
| 8 | Hidden lists in ad-hoc mode | Always applied (global preferences). "X hidden by your filters" line under results. |
| 9 | Applied jobs from earlier searches show up again | Keep the Unapplied/All/Applied tabs. Surface "includes 3 already applied" hint when applied count > 0 in Unapplied tab. |

## Build order

1. **Backend — `seen_jobs` store + detail/letter migration.** Ground floor; everything else depends on it.
2. **Backend — `POST /jobs/search`** (async, mirrors refresh). New `SearchSpec` schema. Pipeline runs against the spec, writes results to `seen_jobs` and to a per-user `last_search_snapshot`.
3. **Frontend — home page rebuild.** Three blocks: Resume card → Search form (What/Where required, More filters collapsed for salary/employment/posted) → Results (existing JobCard + tabs).
4. **Frontend — Settings rename.** "Saved searches" → "Daily auto-search" with the new framing copy. Add "Save as daily" affordance on the home form.
5. **Quota awareness** *(deferred until close to cap)*. Track per-user JSearch usage and surface a hint when low.

## Status

| Step | Status |
|---|---|
| 1. `seen_jobs` store | shipped (1da8df5) |
| 2. Detail/letter migrate | shipped (1da8df5) |
| 3. `POST /jobs/search` | shipped (2f6cb1b) |
| 4. Home page rebuild | shipped (9e794c9) |
| 5. Settings rename + "Save as daily" | shipped |
| 6. Quota awareness | deferred |

## Out of scope (revisit later)

- Search history beyond "last search".
- Cosmos DB / Blob Storage migration (Phase 7 deploy).
- Daily scheduler — the cron/timer that actually runs saved searches automatically. The reframe in step 4 is preparation for this.

---

# Plan: Apply Kit

A side panel on the Job Detail page that surfaces resume, cover letter,
and profile fields as copy-paste-ready chunks while the employer's
apply page is open in a side window. **Manual apply, but with the
friction removed.** Not browser automation, not auto-submit.

## Why this and not full autopilot

We considered a Claude computer-use / browser-use agent that drives the
employer page automatically. Decision: **out of scope for this project.**
- Brittle: Workday and custom employer ATSes break agentic flows ~30%
  of the time.
- Costly: $0.20–$2 per submission in tokens; needs a paid Azure tier
  to host headless Chromium.
- TOS exposure: LinkedIn/Indeed forbid automation; many employers flag
  obvious bot submissions and auto-reject.
- Bad reputation tradeoff: low-quality auto-apps waste recruiter time
  and hurt the user.

The Apply Kit gets ~80% of the daily-life benefit (no tab-switching,
no retyping, no hunting for the resume file) without any of those
risks. User stays in control; employer never sees automation.

## Shape

Two-column layout on the Job Detail page (lg breakpoint and up). Left
column unchanged (JD + cover letter workspace). New right column:
**ApplyKitPanel** with three sections:

1. **Resume** — filename + Download button + "Open in new tab" button.
2. **Cover letter** — version selector dropdown + Copy text + Download .md.
3. **Profile fields** — Name, Email, Phone, City, LinkedIn, GitHub,
   Portfolio, each with a 📋 copy-to-clipboard button.

Below the three sections: **"Open posting in side window"** button that
opens `job.url` as a popup pinned next to the browser
(`window.open(url, "posting", "popup,width=720,height=900")`), so the
user can paste from the kit into the employer's form without losing
the kit's context.

## Architecture

The panel is **read-only** over data the app already has:

| Section          | Data source            | Already exists? |
|------------------|------------------------|-----------------|
| Resume           | `useResume()`          | yes (Settings)  |
| Cover letter     | `useLetterVersions()`  | yes (workspace) |
| Profile fields   | `useProfile()`         | yes (Settings)  |

Copy buttons use `navigator.clipboard.writeText()` — browser-native, no
backend. No new endpoints, no schema changes. Roughly one new component
(`ApplyKitPanel.tsx`) and a layout tweak in `JobDetailPage.tsx`.

## Build order

1. **`ApplyKitPanel.tsx`** — render the three sections from existing
   hooks. Copy-to-clipboard buttons with toast feedback. Disabled
   states when data is missing (no resume → "Upload one in Settings").
2. **JobDetailPage layout** — switch to `lg:grid-cols-3` (left col 2/3,
   right col 1/3). Move existing Strategy + Critique into the
   ApplyKitPanel column above the new sections, OR keep them separate
   and stack.
3. **"Open posting in side window" button** — replace or augment the
   existing "View posting" button so it opens as a popup instead of a
   tab. Keep the tab-open as a fallback for browsers that block popups.
4. **Polish** — keyboard shortcut to copy each field (e.g., `c, e` for
   email), "missing field" hints when profile is incomplete.

## Status

| Step | Status |
|---|---|
| 1. ApplyKitPanel component | shipped |
| 2. JobDetail two-column layout | shipped (existing layout reused) |
| 3. Side-window popup button | shipped |
| 4. Polish | not started |

## Optional v2 add-ons (decide later)

- **"Why are you interested?" generator** — small dialog calling Claude
  with the JD + resume to draft a 3-sentence answer to the most common
  screening question. Reuses the existing Anthropic client. Probably
  $0.01 per generation.
- **Greenhouse / Lever direct apply** — when `job.url` matches their
  board patterns, show a "Direct apply available" badge and submit via
  their public APIs from the backend. Skips the manual paste loop on
  the ~10–20% of postings that use these ATSes.
- **Browser extension** — same UI as the panel, but injected into the
  employer page so paste happens automatically on focus. Only worth it
  after the panel is proven daily-useful.

## Out of scope (the autopilot path, revisit only if explicitly chosen)

- Headless-browser agent that submits applications.
- Captcha solving.
- Login automation for LinkedIn / Indeed / etc.
- Auto-answer to free-text screening questions beyond a single
  one-shot generator with manual review.
