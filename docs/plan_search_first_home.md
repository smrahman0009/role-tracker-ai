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
| 1. `seen_jobs` store | not started |
| 2. `POST /jobs/search` | not started |
| 3. Home page rebuild | not started |
| 4. Settings rename + "Save as daily" | not started |
| 5. Quota awareness | deferred |

## Out of scope (revisit later)

- Search history beyond "last search".
- Cosmos DB / Blob Storage migration (Phase 7 deploy).
- Daily scheduler — the cron/timer that actually runs saved searches automatically. The reframe in step 4 is preparation for this.
