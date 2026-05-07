# Interactive cover letter generation, plan

A user-in-the-loop redesign of the cover letter flow. Replaces the
existing fire-and-forget agent loop (planner, critic, revise) with a
shorter loop that surfaces the agent's reasoning as inspectable
artifacts and lets the user steer at each decision point.

The existing flow is preserved as an alternate mode for the case
where the user wants a one-shot draft.

---

## Why this exists

The current agent loop ships a single letter using its own judgment
about which story to tell. When the agent picks the wrong story,
refinement does not fully fix it, because the planner has already
committed to a strategy. The user wants control at the strategy
level, not just the polish level.

This redesign also addresses a related problem: cover letters are
shorter than the agent currently knows how to generate, and they
should sound like the writer rather than the model. The fix is a
deterministic style validator on every output and tighter prompts
on smaller paragraph slices.

---

## Reference template

All paragraph generation anchors on this user-supplied template, kept
short on purpose:

```
Paragraph 1, Introduction & Hook
Hi {hiring_manager}, I'm {user.name}, a {user.role} with
{user.experience_summary}. I'm genuinely excited about the
{job.title} role at {job.company} because of your focus on
{excitement_hook}.

Paragraph 2, Why You're a Fit
[Strong match path]
Your role requires {req_1} and {req_2}. In my work at
{relevant_employer}, I built {specific_example} that directly
demonstrates {req_1}. Additionally, I've shipped {relevant_skill},
which aligns with your need for {req_2}.

[Gap path]
Your role requires {req_1} and {req_2}. I have strong experience
with {req_1} from my work at {relevant_employer}. While my {req_2}
experience is still developing, I'm actively building this skill
through {growth_evidence}, and my foundation in
{transferable_skill} positions me to ramp up quickly.

Paragraph 3, Close
{user_self_summary_one_liner}. I'd love to connect and explore how
I can contribute to your team. Thank you for your time and
consideration.
Best,
{user.first_name}
```

The prompts in `cover_letter/prompts/` use this as the structural
constraint. The match analysis from Phase 1 supplies the variables:
Strong matches drive the strong-match path of Paragraph 2, Gaps
drive the gap-honest path, Partial matches inform the framing of
either, and `excitement_hooks` (added below) feed Paragraph 1.

---

## The user flow

Three pages, no wizard, all on one screen as a single editor.

1. **Match analysis (top of page).** Three short bullet lists: Strong
   matches, Gaps, Partial matches. Generated once per (resume, JD)
   pair and cached. Plain text, no clusters, no summaries.

2. **Three paragraphs of the letter (middle of page).** Each
   paragraph card has three lifecycle states:
   - *Viewing*: agent's default text, plus two buttons.
     "Try different angle" generates an alternative. "Tweak this"
     enters edit mode.
   - *Tweaking*: the paragraph text becomes an editable textarea.
     Save commits the edit, Cancel reverts.
   - *Committed*: the paragraph is locked, with a small "Edit again"
     link. Once all three are committed, the Finalize button enables.

3. **Side-by-side compare (when user clicks "Try different angle").**
   The current paragraph stays on the left; the alternative appears
   on the right. The user picks one or asks for another alternative.
   No more than three alternatives stored at any time (the oldest
   gets dropped as new ones arrive).

4. **Per-card optional steering hint.** A small "Customize this
   paragraph" link below each card opens a single-line input. The
   user types something like "lead with Everstream supply-chain
   ML work, not LLM stuff." That hint is included in the prompt
   for the next regeneration of that paragraph only.

5. **Finalize.** When all three paragraphs are committed, clicking
   Finalize runs one Sonnet smoothing pass on the assembled letter
   and persists it to the existing letters table with `edited_by_user
   = True`. The smoothing pass enforces tone consistency across
   paragraphs and runs the style validator one more time on the
   final output.

The existing "Generate with the agent" flow stays in the UI as a
secondary button on the same page. Two modes, user picks which.

---

## Architecture

```
                            POST /cover-letter/analysis
                            ─────────────────────────
                            cache hit?  yes → return cached
                                        no  → Haiku call → cache → return

                            POST /cover-letter/draft
                            ─────────────────────────
                            paragraph = hook | fit | close
                            input = resume + JD + analysis +
                                    committed_paragraphs + hint
                            Haiku call → style validator → return

                            POST /cover-letter/finalize
                            ─────────────────────────
                            input = three committed paragraphs
                            Sonnet smoothing call →
                              style validator →
                              save to letters table → return
```

Three endpoints. No background tasks. No agent loop. Each call is
synchronous, predictable, and idempotent in the sense that you can
retry a failed call without breaking state.

---

## Storage

| What | Where | Why |
|------|-------|-----|
| Match analysis | New attribute `match_analysis` on the existing seen-jobs DynamoDB item | One analysis per (user, job). Cached on the natural pair. |
| Cache key | sha256(resume_text) plus sha256(jd_text), stored alongside the analysis | Recompute on resume change or JD change, hit cache otherwise. |
| Drafts and alternatives | Frontend state only (React + localStorage backup) | Ephemeral until committed. No reason to persist server-side. |
| Committed letter | Existing letters DynamoDB table | Same as today. `edited_by_user = True`, `strategy = None` (the user is the strategy). |

No new tables. The existing data model already covers everything.

---

## API shapes

### POST /users/{user_id}/jobs/{job_id}/cover-letter/analysis

```json
// response
{
  "strong": [
    "Python, 5 yrs (JD asks 3+)",
    "LLM agent loops shipped to prod (JD asks experience with agentic systems)"
  ],
  "gaps": [
    "Kubernetes (JD requires; resume shows Docker only)",
    "Direct customer-facing experience (JD asks 2+ yrs)"
  ],
  "partial": [
    "Distributed systems, 1 yr (JD asks 3+; related Spark work compensates)"
  ],
  "excitement_hooks": [
    "their focus on real-time inference at scale",
    "the cross-functional collaboration between ML and product"
  ],
  "cached": false,
  "model": "claude-haiku-4-5"
}
```

`excitement_hooks` are 2-3 candidates Paragraph 1 can pick from. Each
is one short phrase fitting the template's
"because of your focus on ___" slot.

### POST /users/{user_id}/jobs/{job_id}/cover-letter/draft

```json
// request
{
  "paragraph": "hook",
  "committed": {
    "hook": null,
    "fit": null,
    "close": null
  },
  "hint": "lead with the Everstream supply-chain ML work",
  "alternative_to": null
}

// response
{
  "text": "Hi Hiring Manager, I'm Shaikh Rahman...",
  "model": "claude-haiku-4-5",
  "tokens": { "input": 1240, "output": 128 }
}
```

`alternative_to` is set to the current paragraph text when generating
a side-by-side variant, so the prompt can include "give me a
different angle than this."

### POST /users/{user_id}/jobs/{job_id}/cover-letter/finalize

```json
// request
{
  "hook": "...",
  "fit": "...",
  "close": "..."
}

// response: same shape as the existing Letter response, with version
// auto-assigned by the letters store and edited_by_user = True
```

---

## Backend pieces

```
src/role_tracker/cover_letter/
  interactive.py            ← new module, three pure functions:
                              analyze(resume, jd) -> Analysis
                              draft(resume, jd, analysis, committed, hint, alt) -> str
                              finalize(hook, fit, close) -> str
  style_validator.py        ← new module, runs after every LLM call
  prompts/
    interactive_analysis.py ← system prompts as code
    interactive_hook.py
    interactive_fit.py
    interactive_close.py
    interactive_smooth.py

src/role_tracker/api/routes/
  letters.py                ← three new endpoints, gated by the
                              existing get_letter_store dependency
                              for the finalize-time write
```

The existing `cover_letter/agent.py`, `cover_letter/critique.py`,
`cover_letter/refine.py`, etc. all stay untouched. The new flow is
additive, not a replacement.

---

## Style validator (the post-processor)

A deterministic regex-and-substitution sweep that runs on every
LLM-produced string before it is shown to the user or sent further
down the pipeline. Catches things prompting cannot reliably enforce.

```python
# style_validator.py

_BANNED_PHRASES = [
    "delve into", "dive into", "navigate the landscape",
    "it's worth noting", "I'd be remiss",
    "leverage", "harness", "unlock",
    "in the realm of", "at the end of the day",
    "Fundamentally,", "Ultimately,",
]

def clean(text: str) -> str:
    # 1. Replace em-dashes (— and –) with regular punctuation.
    text = text.replace(" — ", ", ").replace("—", ", ")
    text = text.replace(" – ", ", ").replace("–", "-")

    # 2. Drop banned phrases (case-insensitive, preserve sentence flow).
    for phrase in _BANNED_PHRASES:
        text = _strip_phrase(text, phrase)

    # 3. Collapse double spaces left over from substitutions.
    text = re.sub(r" +", " ", text)
    text = re.sub(r" ([,.!?])", r"\1", text)

    return text.strip()
```

Tested with deterministic fixtures. The exact banned list lives in
the module so it is one place to edit when new tics appear.

---

## Phases

Each phase is shippable on its own. Each phase ends with the app
fully working, just with fewer features. None of them require a new
deployment of the existing flow.

### Phase 1, match analysis

1. New endpoint, new module, new tests.
2. Cache check against the seen-jobs item attributes.
3. Frontend page section that calls the endpoint and renders the
   three lists. No card UI yet.
4. Style validator skeleton committed but only used on the analysis
   bullets at first, to prove the pipeline works.

Verifiable on its own: open a job page, see the analysis populate.

### Phase 2, default cards

1. `draft` endpoint with `paragraph` and `committed` only (no hint,
   no alternatives yet).
2. Frontend renders three cards in sequence: Hook generates first,
   then Fit when Hook is committed, then Close when Fit is committed.
3. Each card has only the "Tweak this" button (inline edit + save).
4. No alternatives, no hints.
5. Save flow assembles the three paragraphs as is and writes to the
   letters table. Skip the smoothing pass.

Verifiable on its own: end-to-end interactive draft, no fancy UI.

### Phase 3, alternatives

1. `draft` endpoint accepts `alternative_to`.
2. Frontend "Try different angle" button shows side-by-side compare,
   user picks one to commit.
3. Cap of three stored alternatives per card; oldest drops first.

### Phase 4, steering hints

1. `draft` endpoint accepts `hint`.
2. Frontend "Customize this paragraph" link with a single-line input.
3. Hint applies to the next regeneration of that card only.

### Phase 5, style validator on every output

1. Wire `clean()` into all three endpoints.
2. Tests for each banned phrase and each em-dash variant.
3. Add a small frontend indicator when the validator made
   substitutions ("style cleaned: 2 substitutions"), purely for
   transparency during the early life of the feature.

### Phase 6, Sonnet smoothing pass

1. `finalize` endpoint runs the smoothing pass.
2. Style validator runs again on the final output.
3. Letters table write happens here, not earlier.
4. Frontend Finalize button enables only when all three paragraphs
   are committed.

---

## Tests

| Layer | What gets tested |
|-------|------------------|
| `interactive.py` | Three pure functions tested against an in-memory Anthropic stub. JSON parsing of analysis output, prompt construction for each paragraph, smoothing pass output shape. |
| `style_validator.py` | Every banned phrase and every em-dash variant has a fixture with a before-and-after pair. Deterministic, no LLM calls. |
| API routes | Standard FastAPI test client, dependency overrides for the letter store and Anthropic client. Verifies the cache hit path on `analysis`. |
| Frontend | Component tests for the card lifecycle (Viewing, Tweaking, Committed) and the side-by-side compare flow. |

Target: roughly 30 to 40 new tests across the four layers.

---

## Cost

Per finished letter, with no regenerations:

| Step | Model | Cost |
|------|-------|------|
| Analysis | Haiku | ~$0.005 (cacheable) |
| Three default cards (Hook, Fit, Close) | Haiku, 3 calls | ~$0.015 |
| Smoothing pass | Sonnet | ~$0.025 |
| **Total** | | **~$0.045** |

Each "Try different angle" click adds about $0.005 (Haiku, one card
regenerated). Typical session with 2 to 3 alternatives sampled lands
around 5 to 7 cents per letter.

For the existing fire-and-forget flow, current cost per letter is
about 5 cents. The interactive flow is comparable, possibly slightly
cheaper because the smoothing pass replaces the existing critique
loop.

---

## Open decisions

These do not block planning, but flag for when we get to them.

1. **What to do when the resume changes mid-session.** A user might
   upload a new resume between Hook and Fit. Cleanest: invalidate
   the cached analysis and prompt the user to regenerate. Friendlier:
   keep going with the old analysis and warn. Default to the cleanest
   option for v1.

2. **Should the existing fire-and-forget flow stay as the default
   button on the job detail page?** My preference is yes for the
   first month, then make the interactive flow the default once the
   feature is stable. Current users have muscle memory.

3. **Long-term, should the existing agent loop be removed?** No.
   Keep it as the second mode for users who want one-shot drafts.
   The portfolio story is "two complementary generation modes,"
   not "we replaced the agent."

4. **Where do the per-card hints live in the persisted letter?**
   Probably nowhere. They are ephemeral steering, not part of the
   final artifact. Could be added to the saved letter record as
   metadata if we ever want analytics on common steering patterns.

---

## Status tracker

Tick as we go.

**Phase 1, match analysis**
- [ ] Endpoint + module + tests
- [ ] Cache wiring on seen-jobs item
- [ ] Frontend analysis section

**Phase 2, default cards**
- [ ] Draft endpoint (basic)
- [ ] Three sequential cards in frontend
- [ ] Inline edit lifecycle (Viewing, Tweaking, Committed)
- [ ] Basic save flow without smoothing

**Phase 3, alternatives**
- [ ] Draft endpoint accepts `alternative_to`
- [ ] Side-by-side compare UI
- [ ] Three-alternative cap

**Phase 4, steering hints**
- [ ] Draft endpoint accepts `hint`
- [ ] "Customize this paragraph" UI
- [ ] One-shot application of the hint

**Phase 5, style validator**
- [ ] `clean()` function with banned list
- [ ] Wired into all three endpoints
- [ ] Substitution-count indicator in UI

**Phase 6, smoothing pass and finalize**
- [ ] `finalize` endpoint with Sonnet pass
- [ ] Letters table write moved here
- [ ] Frontend Finalize button enables logic
