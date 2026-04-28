# Role Tracker — Frontend Wireframes

> Three pages: **Login**, **Job List**, **Job Detail**.
> Designed before any React code is written, per the locked Phase 6 plan.
>
> **Three layers of fidelity in this folder:**
> 1. This README — ASCII layouts + behavioral notes. Structure-only.
> 2. [`design_system.md`](design_system.md) — locked color, typography,
>    spacing, component, and microinteraction tokens. Every React
>    component built in Phase 6 must follow this.
> 3. **HTML mockups** — high-fidelity rendered visuals. Open in browser:
>    - [`job_list_mockup.html`](job_list_mockup.html) (home page + filter chip UI states)
>    - [`job_detail_mockup.html`](job_detail_mockup.html) (single application view)
>    - [`settings_mockup.html`](settings_mockup.html) (resume, contact, saved searches, exclusions)
>
> **Routing summary:**
> - `/login`             → Login page (placeholder; sets auth in localStorage)
> - `/`                  → Job List page (the home page)
> - `/jobs/:job_id`      → Job Detail page (everything for one application)
> - `/settings`          → Settings page (profile, searches, exclusion lists)
>
> **How to view the HTML mockups:** open the `.html` file directly in
> your browser. They use the Tailwind v4 browser script via CDN, so
> there's no build step. You should see a fully styled page that
> reflects the visual feel the React port will match.

---

## Filtering model — important architectural distinction

Two distinct concepts that live in different places in the UI:

**Set once / rarely change → Settings page**
- Resume
- Contact info (header data for letters)
- Saved searches (queries that drive what JSearch fetches)
- Excluded companies / title keywords / publishers (stable lists)

**Adjust while browsing → Job List page (inline filter chips)**
- Job type (combobox; matches against title; suggestions from common roles)
- Location (combobox; matches against location; suggestions from common cities)
- Salary minimum (number input)
- Employment type (multi-select: full-time / part-time / contract / internship)
- Posted within (last 7 / 30 / 90 days)

Filter values become URL query params (`/?type=data-scientist&salary_min=80000`)
so refresh and back/forward work naturally and the URL is shareable.

The `[+ Add filter]` button shows a small popover listing every available
filter. Each active filter renders as an indigo-tinted chip with `✕` to
remove. "Clear all" removes everything. When no filters are set the row
collapses to just the dashed `+ Add filter` button so it doesn't waste
space. See state diagrams at the bottom of `job_list_mockup.html`.

---

## Page 1 — Login (`/login`)

Placeholder authentication. Sets `user_id` and `app_token` in
`localStorage`; no real auth yet.

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                                                                  │
│                                                                  │
│                  ┌────────────────────────────┐                  │
│                  │   Role Tracker             │                  │
│                  │                            │                  │
│                  │  User ID                   │                  │
│                  │  ┌──────────────────────┐  │                  │
│                  │  │ smrah                │  │                  │
│                  │  └──────────────────────┘  │                  │
│                  │                            │                  │
│                  │  API Token                 │                  │
│                  │  ┌──────────────────────┐  │                  │
│                  │  │ ••••••••••••         │  │                  │
│                  │  └──────────────────────┘  │                  │
│                  │                            │                  │
│                  │  ┌──────────────────────┐  │                  │
│                  │  │       Sign in        │  │                  │
│                  │  └──────────────────────┘  │                  │
│                  │                            │                  │
│                  └────────────────────────────┘                  │
│                                                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Behaviour:**
- "Sign in" stores `user_id` and `app_token` in `localStorage` and
  redirects to `/`.
- Token is leaked into the `Authorization: Bearer ...` header on every
  subsequent API call by the API client wrapper.
- If the token is invalid, the next API call returns 401, and the user
  gets bounced back to `/login` with an inline error.

**API calls:** none. Just localStorage writes and a router push.

**State:** `useState` for the two text fields, `useNavigate` to redirect.

---

## Page 2 — Job List (`/`)

The home page. Shows ranked jobs as cards. Includes filter tabs and a
"Refresh jobs" button.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Role Tracker            Last refreshed: 2026-04-28 11:24    [↻ Refresh] │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   [ All ]  [ Unapplied (10) ]  [ Applied (2) ]               [⚙ Settings] │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Software Engineer- Full stack            ★ 0.55     MEDIUM fit  │    │
│  │  Microsoft Canada Inc.   ·   Vancouver, BC   ·   $—              │    │
│  │  Eluta.ca   ·   Posted 2026-04-21                                │    │
│  │                                                                  │    │
│  │  Overview\n\nMicrosoft is a company where passionate innovators  │    │
│  │  come to collaborate, envision what can be and take their…       │    │
│  │                                                                  │    │
│  │                              [View details →]    [Mark applied]  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Senior Data Scientist                    ★ 0.51     HIGH fit    │    │
│  │  Trackunit   ·   Toronto, ON   ·   $130k–$170k                   │    │
│  │  LinkedIn   ·   Posted 2026-04-20                                │    │
│  │                                                                  │    │
│  │  We're hiring a Senior Data Scientist to lead our predictive…    │    │
│  │                                                                  │    │
│  │                              [View details →]    [Mark applied]  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  ... 8 more cards                                                │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Card anatomy

```
┌──────────────────────────────────────────────────────────────────┐
│  TITLE (bold, larger)                ★ MATCH SCORE   FIT BADGE   │
│  Company  ·  Location  ·  Salary range (or "$—" if unknown)      │
│  Publisher  ·  Posted YYYY-MM-DD                                 │
│                                                                  │
│  description_preview (~240 chars, ends at word boundary, "…")    │
│                                                                  │
│                              [View details →]    [Mark applied]  │
└──────────────────────────────────────────────────────────────────┘
```

**Behaviour:**
- Three filter tabs: All, Unapplied (default), Applied. Counts shown.
- "↻ Refresh" kicks off `POST /jobs/refresh`. Banner appears
  ("Refreshing jobs… this takes ~60s") and polls every 3s. When done,
  list re-fetches automatically.
- "View details →" navigates to `/jobs/:job_id`.
- "Mark applied" hits `POST /jobs/{id}/applied` inline; the card moves
  to the Applied tab without a page reload.
- Fit badge color: green (HIGH), yellow (MEDIUM), red (LOW), gray
  (None — no letter generated yet).
- "Last refreshed" timestamp shows when the snapshot was taken.

**API calls:**
- On mount: `GET /jobs?filter={current_filter}` (TanStack Query)
- On filter change: re-fetch with new query param
- On "Refresh": `POST /jobs/refresh` → returns refresh_id → poll
  `GET /jobs/refresh/{id}` until done → invalidate the jobs list
- On "Mark applied": `POST /jobs/{id}/applied` → optimistically update
  local cache → if 409, show toast

**State:** TanStack Query handles all server state. Local `useState`
only for the active filter tab.

---

## Page 3 — Job Detail (`/jobs/:job_id`)

Everything for one application on one page. Header at the top, full JD
collapsible, then either the "Generate" CTA or the latest letter inline.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ← Back to jobs                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Software Engineer- Full stack                                           │
│  Microsoft Canada Inc.   ·   Vancouver, BC                               │
│  Match score 0.55   ·   Fit: MEDIUM   ·   Posted 2026-04-21              │
│  Source: Eluta.ca   ·   [View original posting ↗]                        │
│                                                                          │
│                                       [✓ Mark applied]  [↺ Regenerate]   │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  📄 Job description                                          [▼ Hide]    │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  Overview                                                                │
│  Microsoft is a company where passionate innovators come to              │
│  collaborate…                                                            │
│  (full JD, ~7,500 chars in this case, scrollable)                        │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  ✉ Cover letter                                                          │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│   ┌─────────────────────────────────────┐  ┌─────────────────────────┐   │
│   │                                     │  │  Strategy               │   │
│   │  **Shaikh Mushfikur Rahman**        │  │  ─────────────          │   │
│   │  782-882-0852  ·  smrah@…  ·  Halifax  │  Fit:   MEDIUM         │   │
│   │                                     │  │  Primary: Company Name  │   │
│   │  Hello,                             │  │           Resolution    │   │
│   │                                     │  │  Angle:   "ML production│   │
│   │  The Software Engineer, Full Stack  │  │           ownership…"   │   │
│   │  role on Microsoft Canada's OneLake │  │                         │   │
│   │  team caught my attention…          │  │  Critique               │   │
│   │                                     │  │  ─────────────          │   │
│   │  …                                  │  │  Score: 98/110          │   │
│   │                                     │  │  Verdict: approved      │   │
│   │  Best,                              │  │  Hallucination: 25/25   │   │
│   │  Shaikh Mushfikur Rahman            │  │  Tailoring:    18/20    │   │
│   │                                     │  │  Voice:        13/15    │   │
│   │                                     │  │  ...                    │   │
│   └─────────────────────────────────────┘  └─────────────────────────┘   │
│                                                                          │
│   Version: [v3 ▾]   270 words   Created 2026-04-28 14:32                 │
│                                                                          │
│   [Download as Markdown]   [Print → Save as PDF]                         │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  ✏️ Refine                                                                │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│   ┌──────────────────────────────────────────────────────────────────┐   │
│   │ Make it more technical and add a sentence about the embedding   │   │
│   │ work I did on commodity classification.                         │   │
│   │                                                                  │   │
│   └──────────────────────────────────────────────────────────────────┘   │
│   5–500 chars · strategy stays locked · creates a new version            │
│                                                                          │
│                                                          [Refine letter] │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### When NO letter exists yet (first visit)

The "Cover letter" section collapses to:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ✉ Cover letter                                                          │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│   No letter yet for this job.                                            │
│                                                                          │
│                                            [✨ Generate cover letter]    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### When generation is in flight

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ✉ Cover letter                                                          │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│   ⏳ Generating letter…                                                   │
│      Reading job description…                                            │
│      Looking up resume sections…                                         │
│      Drafting and reviewing against rubric…                              │
│                                                                          │
│   This takes about 30-60 seconds.                                        │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ (animated progress bar)        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Behaviour:**
- "Generate cover letter" → `POST /jobs/{id}/letters` → returns
  generation_id → poll `GET /letter-jobs/{id}` every 3s until done.
  When done, the section re-renders with the letter inline.
- "Regenerate" → same flow but the user sees a confirmation modal
  ("This will discard the current strategy and start fresh. Continue?"),
  then `POST /jobs/{id}/regenerate`.
- "Refine letter" → `POST /jobs/{id}/letters/{version}/refine` with the
  feedback in the body. Same async pattern. The new version becomes the
  one displayed; the old version is still accessible via the version
  selector.
- "v3 ▾" version selector dropdown lists all saved versions. Selecting
  one swaps the displayed letter without navigation.
- "Mark applied" / unmark via the header button — toggles inline.
- "Download as Markdown" hits `GET .../letters/{v}/download.md` (browser
  saves the file).
- "Print → Save as PDF" triggers `window.print()` with print-friendly
  CSS (the rest of the UI hides; only the letter prints).

**API calls (all per visit):**
- On mount: `GET /jobs/{id}` and `GET /jobs/{id}/letters`
- On generate / regenerate / refine: as described above
- On version selector change: data already in memory from the
  letters list call

**State:**
- TanStack Query for: job detail, letter versions list,
  generation poll status
- Local `useState` for: collapsed-JD toggle, refine textarea content,
  selected version (if not the latest)

---

## User flow

```
                      ┌──────────────────┐
                      │      Login       │
                      │  /login          │
                      └────────┬─────────┘
                               │
                               │ sets user_id + token in localStorage
                               ▼
              ┌────────────────────────────────────┐
              │           Job List                 │
              │           /                        │
              │                                    │
              │  Lists all ranked jobs as cards    │
              │  Filter: All / Unapplied / Applied │
              │  Refresh button                    │
              └─────────────┬──────────────────────┘
                            │
                            │ click "View details →"
                            ▼
              ┌────────────────────────────────────┐
              │          Job Detail                │
              │          /jobs/:job_id             │
              │                                    │
              │  Full JD                           │
              │  Generate / Refine / Regenerate    │
              │  Strategy + critique panel         │
              │  Version history                   │
              │  Mark applied                      │
              └────────────────────────────────────┘
```

---

## Component breakdown (informational, not authoritative)

This is what we'll likely end up with. The exact structure may shift.

```
src/
  pages/
    LoginPage.tsx
    JobListPage.tsx
    JobDetailPage.tsx
  components/
    ui/                     ← shadcn/ui generated components
      button.tsx
      card.tsx
      input.tsx
      tabs.tsx
      ...
    JobCard.tsx             ← one card on the list page
    FitBadge.tsx            ← color-coded HIGH/MEDIUM/LOW pill
    LetterViewer.tsx        ← markdown-rendered letter
    StrategyPanel.tsx       ← strategy + critique sidebar
    RefineForm.tsx          ← textarea + button
    GenerationProgress.tsx  ← the "generating…" indicator
    Layout.tsx              ← top nav, main wrapper
  lib/
    api.ts                  ← typed fetch wrapper, includes bearer token
    auth.ts                 ← localStorage get/set/clear
  hooks/
    useJobs.ts              ← TanStack Query for jobs list
    useJobDetail.ts
    useLetterVersions.ts
    useGenerateLetter.ts    ← starts generation + polls
  App.tsx
  main.tsx
```

---

## Styling notes

- **Tailwind CSS** for layout, spacing, color
- **shadcn/ui** for prebuilt components (Button, Card, Input, Tabs,
  Dialog, Toast, etc.)
- **Color palette**: pick when scaffolding lands. Default to shadcn's
  "neutral" with one accent color (probably Tailwind's `indigo` or
  `emerald`).
- **Mobile responsive**: cards stack to one column under 768px;
  strategy panel moves below the letter on detail page.
- **Dark mode**: nice-to-have for Phase 9 polish, not required earlier.

---

## What this wireframe is NOT yet

- **No real visual design** — colors, exact spacing, font sizes will be
  decided when we start writing components.
- **No empty / error states** for things beyond what's shown — TanStack
  Query gives us standard loading/error UX out of the box.
- **No accessibility detail** — keyboard nav, ARIA labels, focus rings
  all come naturally with shadcn/ui defaults.

If you want changes to ANY of the above before we write code, edit this
file directly or comment on it. Once the scaffolding lands, the
wireframe stays here as the reference for what's being built toward.
