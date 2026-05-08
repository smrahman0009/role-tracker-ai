# Cover-letter generate dialog — design plan

Replaces both:

- The per-paragraph "interactive cards" flow that lived in
  `CoverLetterAnalysisPanel` + `CoverLetterDraftPanel` + the
  `/cover-letter/{analysis, draft, finalize}` routes.
- The chat-driven flow explored in `feat/cover-letter-chat` (Phases
  1–2 of `docs/cover_letter_chat_plan.md`). That work stays in git
  history but is not merged.

## Goal

When the user clicks **Generate**, open a small dialog that lets
them give optional natural-language steering — an instruction
("make it punchy, mention my fintech work") and/or a style template
(an existing letter to mirror) — then runs the existing agent. If
they leave both empty, it generates exactly like today's one-click
button.

The same dialog handles the iteration case: a radio toggle picks
between *Start from scratch* (calls `/generate`) and *Edit current
draft v3* (calls `/refine` with the chosen feedback). One dialog,
two modes — Cursor's Cmd-K pattern.

A checkbox surfaces Anthropic's **extended thinking** as an opt-in
quality boost. Cost goes from ~$0.05 → ~$0.12; latency 5–10s →
15–30s. Useful for non-obvious resume↔JD matches.

## Out of scope

- Streaming the agent's output (replies are fast enough; nice-to-have
  for v1.1).
- Conversation history / multi-turn back-and-forth (use Refine instead).
- Per-paragraph editing UI (the agent owns full-letter generation;
  paragraph-level edits go through the existing manual-edit flow).
- Saving steering instructions across sessions (each dialog open
  starts fresh).

## UX

### Trigger

Existing **Generate** button on `LetterWorkspace`. No new button,
no second entry point.

### Dialog layout

```
┌─────────────────────────────────────────────────────────────┐
│  Generate cover letter                              [×]     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ◉ Start from scratch                                       │
│  ◯ Edit current draft (v3)         [disabled if no draft]   │
│                                                             │
│  Instructions                                  (optional)   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Make it punchy, mention my fintech work, lead with    │ │
│  │ the LLM project.                                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Style template — paste an existing letter to mirror's      │
│  voice and structure                            (optional)  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Dear hiring manager, ...                               │ │
│  │                                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ☐  Extended thinking — slower, higher quality on         │
│      non-obvious matches (~3× cost)                         │
│                                                             │
│            [ Cancel ]      [ Generate ]                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Behaviour

- **First open**: instruction + template empty, mode = scratch,
  extended thinking off. Click Generate → runs identical to today's
  one-click flow.
- **With instruction**: the agent's system prompt gets prepended with
  "User-supplied steering: <instruction>". The agent treats it as
  high-priority guidance.
- **With template**: appended to the system prompt as
  "Mirror the voice, length, and structure of this previous letter
  (use facts only from THIS resume + JD): <template>".
- **Edit mode**: dialog calls `/refine` instead of `/generate`,
  passing the instruction as the feedback string. The current draft
  comes from `LetterWorkspace.current`. Mode is disabled when no
  draft exists yet.
- **Extended thinking on**: backend passes `thinking={"type":
  "enabled", "budget_tokens": 10_000}` to the Anthropic client, and
  records `cover_letter_generate_extended` (cost ~$0.12) instead of
  `cover_letter_generate`.

### Iteration model

User clicks Generate → fills dialog → gets v1. Wants it shorter →
re-opens dialog, picks "Edit current draft (v1)", types "shorter,
cut paragraph 2 to one sentence" → gets v2. Repeat. Each generation
creates a new version; the version selector lets users compare.

This is **Option B** from earlier discussion: Refine isn't a
separate button anymore — it's the second mode inside the single
dialog. The `/refine` route stays unchanged.

## Backend

### Modified routes

```
POST /users/{user_id}/jobs/{job_id}/letters
     Body adds (all optional):
       instruction        : str | None    (user steering, up to 500 chars)
       template           : str | None    (style sample, up to 4000 chars)
       extended_thinking  : bool = False

POST /users/{user_id}/jobs/{job_id}/letters/{version}/refine
     Already takes `feedback`. Body adds:
       extended_thinking  : bool = False
     (`feedback` itself fills the role of instruction here.)
```

Both wire the new fields into the existing agent. The agent's
system prompt builder gets two new optional sections:

```
{base system prompt}

{when instruction is set:}
USER STEERING (treat as high-priority guidance, but do not invent
facts to satisfy it):
<instruction>

{when template is set:}
STYLE TEMPLATE (mirror the voice, length, paragraph structure of
this letter, but write the content using only facts from this
resume and this job description):
<template>
```

### Cost tracking

New entry in `FEATURE_COST_USD`:

```python
"cover_letter_generate_extended": 0.12,
```

Added to `ANTHROPIC_FEATURES`. The route picks which feature name to
record based on the `extended_thinking` flag. Daily-cap math
automatically picks up the higher cost.

### Removed

The card-flow routes and module:

- `POST /cover-letter/analysis` and supporting code
- `POST /cover-letter/draft` and supporting code
- `POST /cover-letter/finalize` and supporting code
- `cover_letter/interactive.py` is trimmed to keep only
  `summarize_job`, `resolve_model`, `JobSummary`, `SummaryError`
  (the JD summary panel still uses these)
- The per-paragraph prompt files in `cover_letter/prompts/`
- Their schema models (`CoverLetterAnalysisResponse`,
  `CoverLetterDraftRequest`, `CoverLetterDraftResponse`,
  `CoverLetterFinalizeRequest`, `CoverLetterCommitted`)

The `cover_letter_polish` and `why_interested_*` routes stay —
they're independent surfaces.

## Frontend

### New

- `GenerateLetterDialog.tsx` — a Radix Dialog with the layout above.
  Owns its own form state. Calls either `useGenerateLetter()` or
  `useRefineLetter()` based on the mode toggle.
- A small adjustment to `LetterWorkspace.tsx` so the Generate button
  opens the dialog instead of immediately kicking off generation.

### Removed

- `CoverLetterAnalysisPanel.tsx`
- `CoverLetterDraftPanel.tsx`
- `useCoverLetterAnalysis.ts`
- `useCoverLetterDraft.ts`
- The matching types (`CoverLetterDraftRequest`,
  `CoverLetterDraftResponse`, `CoverLetterFinalizeRequest`,
  `CoverLetterAnalysisResponse`, `CoverLetterCommitted`).
- The standalone Refine button on the page (route stays for the
  dialog to call). The existing `RefineDialog.tsx` is kept for now
  because it's imported elsewhere; future cleanup can fold it in.

`JobSummaryPanel.tsx` and the one-click letter generation path stay
exactly as they are.

## Phases

### Phase 1 — Cleanup ✅ Done

Per-paragraph card flow removed: frontend cards + hooks + types;
backend routes (`/cover-letter/analysis`, `/draft`, `/finalize`);
the `cover_letter.interactive` module trimmed to summary-only;
their schemas and tests.

### Phase 2 — Backend ✅ Done

`GenerateLetterRequest` gained `instruction`, `template`, and
`extended_thinking`. `RefineLetterRequest` gained
`extended_thinking`. Both threaded through to the agent's prompt
and (for thinking) the Anthropic call. New
`cover_letter_generate_extended` cost entry ($0.12) and per-user
cap override (`DAILY_COST_CAP_USD_OVERRIDES` env var).

### Phase 3 — Frontend dialog ✅ Done

`GenerateLetterDialog.tsx` shipped. Mode radio (scratch / edit
current draft), instruction textarea, template textarea (scratch
mode only), extended-thinking checkbox. Wired into `LetterWorkspace`
as the **only** entry point — Regenerate and Refine buttons removed.

### Phase 3.5 — Polish (added live based on feedback) ✅ Done

- Single Generate button (consolidated three buttons → one)
- ATS-friendly URL rendering in the contact header
- Live progress phase labels during generation ("Searching your
  resume…", etc.) via an `on_phase` callback from the agent
- Off-topic deflection paragraph in the agent's system prompt
- Per-user daily-cap override

### Phase 4 — Real-job prompt iteration ⏳ Pending

Run the dialog against several real job postings; tune the agent's
system prompt where outputs feel weak. **Not started** — only
meaningful with real Anthropic calls + real JDs.

## Estimate

**~1.5 days focused work.** The chat plan needed ~4 days; this is
significantly less because:

- No conversation persistence
- No SSE streaming
- No per-conversation turn caps
- No DynamoDB chat table
- No tool-use parsing

## Open questions

None blocking implementation. Two flagged for during-build:

- **How big should the template textarea be by default?** Probably
  ~6 rows, expandable.
- **Should the dialog remember its last-used values per job?**
  No — too easy to accidentally re-use stale guidance. Each open
  starts fresh.
