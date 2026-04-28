# Role Tracker — Design System

> The single source of truth for visual decisions. Every React component
> built in Phase 6 should follow these tokens and patterns. If something
> in code feels "off" visually, this doc is the reference to bring it
> back to.
>
> **Status:** approved 2026-04-28. Deviations from this doc require
> explicit re-discussion.

---

## Design philosophy (three bullets)

1. **Calm, not flashy.** Whitespace and typography do the work. Color is
   restrained — one accent, status badges only where they signal something.
2. **Density when it matters.** Power users want information, not breathing
   room. Cards are tight (16-20px padding). Lists are scannable.
3. **Restraint is the polish.** Premium feel comes from consistency and
   discipline, not from animation libraries or decorative elements.

The reference apps that nail this: **Linear, Vercel, Stripe Dashboard,
Notion**. We're not copying any of them, but we're operating in the same
visual vocabulary.

---

## Color tokens

All colors are Tailwind v4 OKLCH values — they produce more perceptually
even steps than HSL. We use Tailwind class names; the hex equivalents are
listed for reference only.

### Surface

| Token              | Tailwind class    | Hex (approx) | Used for                          |
| ------------------ | ----------------- | ------------ | --------------------------------- |
| Page background    | `bg-slate-50`     | `#f8fafc`    | The body / outer scroll container |
| Card surface       | `bg-white`        | `#ffffff`    | All cards, panels, modals         |
| Card border        | `border-slate-200`| `#e2e8f0`    | 1px hairline only — no heavy borders |
| Subtle inset       | `bg-slate-100`    | `#f1f5f9`    | Code chips, score badges, table headers |

### Text

| Token              | Tailwind class    | Used for                                |
| ------------------ | ----------------- | --------------------------------------- |
| Primary            | `text-slate-900`  | Headings, body copy users actually read |
| Secondary          | `text-slate-600`  | Metadata, supporting text, descriptions |
| Tertiary           | `text-slate-400`  | Timestamps, very low-priority labels    |
| On dark            | `text-white`      | Primary buttons                         |

### Accent (one only)

| Token   | Tailwind class      | Hex       | Used for                            |
| ------- | ------------------- | --------- | ----------------------------------- |
| Primary | `bg-indigo-600`     | `#4f46e5` | Primary buttons, focused states     |
| Hover   | `bg-indigo-700`     | `#4338ca` | Primary button hover                |
| Subtle  | `text-indigo-600`   | `#4f46e5` | Links, "View details" inline action |

**Why indigo and not violet:** violet/purple has become the default "AI app"
color (Anthropic, OpenAI, Cursor all lean violet). Indigo reads as
classic professional SaaS — closer to Stripe/Vercel than to AI startups.
For a portfolio piece, that's the better signal.

### Status badges (fit assessment)

| Fit      | Badge bg          | Badge text            | Border             |
| -------- | ----------------- | --------------------- | ------------------ |
| HIGH     | `bg-emerald-50`   | `text-emerald-700`    | `border-emerald-200` |
| MEDIUM   | `bg-amber-50`     | `text-amber-700`      | `border-amber-200`   |
| LOW      | `bg-rose-50`      | `text-rose-700`       | `border-rose-200`    |
| (None)   | `bg-slate-100`    | `text-slate-500`      | `border-slate-200`   |

Pill style: `px-2 py-0.5 rounded-full text-xs font-medium border`.

### Score chip

Match score is shown as a chip:
`bg-slate-100 text-slate-900 px-2 py-0.5 rounded-md text-xs font-medium tabular-nums`.

---

## Typography

### Font stack

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
             "Helvetica Neue", Arial, sans-serif;
```

System UI: fast, native feel, $0 cost. We do NOT load Inter or any
custom font — the speed-and-restraint philosophy means no font flash.

### Scale

| Use                          | Tailwind         | Approx px | Weight |
| ---------------------------- | ---------------- | --------- | ------ |
| Page title (e.g. "Role Tracker") | `text-2xl`   | 24        | 600    |
| Section heading              | `text-lg`        | 18        | 600    |
| Card title (job title)       | `text-base`      | 16        | 600    |
| Body                         | `text-sm`        | 14        | 400    |
| Metadata                     | `text-xs`        | 12        | 500    |
| Numeric (scores, counts)     | `font-medium tabular-nums` | varies | 500 |

### Rules

- **Never use weight 700 (`font-bold`) for headings.** 600 (`font-semibold`)
  reads as more modern and confident.
- **Letter-spacing**: default for body, `tracking-tight` (-0.025em) for
  large display text only.
- **Line-height**: `leading-relaxed` (1.625) for body, `leading-tight` (1.25)
  for headings.

---

## Spacing scale

Tailwind defaults — we don't customize. Common rhythm:

- Inside cards: `p-5` or `p-6` (20-24px)
- Between cards: `gap-3` or `gap-4` (12-16px)
- Page gutters: `px-6` desktop, `px-4` mobile
- Vertical section spacing: `py-8`

Use multiples of 4. Don't invent in-between values.

---

## Layout patterns

### Page shell

```
┌─────────────────────────────────────────────┐
│  Top header (h-14, bg-white, border-b)       │
├─────────────────────────────────────────────┤
│  max-w-5xl mx-auto px-6 py-8                 │
│  (content)                                   │
└─────────────────────────────────────────────┘
```

- Header: white background, `border-b border-slate-200`, `h-14` (56px tall),
  flex with brand on the left and user/settings on the right.
- Content max-width: `5xl` (1024px) for list, `4xl` (896px) for detail.
- Content side gutters: `px-6` desktop, `px-4` on mobile.

### Card

```
┌──────────────────────────────────────────────────────┐
│ p-5 or p-6 padding                                   │
│ ┌──────────────────────────────────────────────────┐ │
│ │ bg-white                                         │ │
│ │ border border-slate-200                          │ │
│ │ rounded-xl                                       │ │
│ │ shadow-sm                                        │ │
│ │ hover:shadow-md hover:-translate-y-0.5           │ │
│ │ transition-all duration-200                      │ │
│ └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

Always:
- `bg-white`
- `border border-slate-200`
- `rounded-xl` (12px corners)
- `shadow-sm` resting; `shadow-md -translate-y-0.5` on hover
- `transition-all duration-200`

Never:
- Heavy `shadow-lg` or `shadow-xl` (Material territory)
- Borders heavier than 1px
- Border-radius bigger than `rounded-2xl` (looks bubbly)

---

## Component patterns

### Primary button

```html
<button class="
  inline-flex items-center gap-1.5
  px-4 py-2 rounded-lg
  bg-indigo-600 text-white text-sm font-medium
  hover:bg-indigo-700
  active:bg-indigo-800
  disabled:bg-slate-300 disabled:cursor-not-allowed
  transition-colors duration-150
">
  Generate cover letter
</button>
```

### Secondary button

Same shape, different colors:
```
bg-white border border-slate-200 text-slate-700
hover:bg-slate-50 hover:border-slate-300
```

### Filter tabs

```html
<div class="flex gap-1 border-b border-slate-200">
  <button class="px-4 py-2 text-sm font-medium text-slate-900 border-b-2 border-indigo-600">
    Unapplied <span class="text-slate-400 ml-1">10</span>
  </button>
  <button class="px-4 py-2 text-sm font-medium text-slate-500 border-b-2 border-transparent hover:text-slate-700">
    All <span class="text-slate-400 ml-1">12</span>
  </button>
  <button class="px-4 py-2 text-sm font-medium text-slate-500 border-b-2 border-transparent hover:text-slate-700">
    Applied <span class="text-slate-400 ml-1">2</span>
  </button>
</div>
```

The active tab gets a 2px `border-indigo-600` underline. Inactive tabs
have transparent borders so the layout doesn't shift.

### Input

```html
<input class="
  w-full px-3 py-2 rounded-lg
  bg-white border border-slate-200
  text-sm text-slate-900 placeholder:text-slate-400
  focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500
" />
```

Subtle focus ring (`ring-indigo-500/20` = 20% opacity). No "loud" outline.

### Skeleton loader

```html
<div class="animate-pulse">
  <div class="h-4 bg-slate-200 rounded w-3/4 mb-2"></div>
  <div class="h-3 bg-slate-200 rounded w-1/2"></div>
</div>
```

Use the SHAPE of the content as the skeleton — don't show a generic spinner.
Stripe and Linear both do this.

---

## Microinteractions

| Where        | Behavior                                    | Duration |
| ------------ | ------------------------------------------- | -------- |
| Card hover   | Lift `-translate-y-0.5` + shadow grows      | 200ms    |
| Button hover | Background color shifts                     | 150ms    |
| Tab switch   | Underline slides between tabs               | 200ms    |
| Input focus  | Ring fades in (20% opacity)                 | 150ms    |
| Modal open   | Fade + small scale-up (95% → 100%)          | 200ms    |
| Toast appear | Slide up + fade in from bottom              | 250ms    |

All easings: `ease-out` (Tailwind default). Never `ease-in` for entry
or `ease-in-out` (feels lazy).

Never:
- Bouncy springs (cubic-bezier with overshoot)
- Rotation tricks
- Long durations (>300ms reads slow)

---

## Iconography

- **Lucide React** (`lucide-react` package) for any icons. It's what
  shadcn/ui uses by default; consistent stroke-based outline style.
- Icon size: `h-4 w-4` for inline-with-text, `h-5 w-5` for buttons.
- Stroke width: default (2). Don't customize.
- Color: inherit from text color. Match the surrounding type.

When NOT to use icons:
- As decoration without a label (every icon should mean something)
- In dense lists where they create visual noise
- Emoji as design — never (one or two informational ones in copy is fine)

---

## Empty states

For "you haven't done X yet" pages:
- Centered vertical layout
- One small icon (Lucide, slate-400)
- Heading (`text-base font-semibold text-slate-900`)
- One sentence of supporting text (`text-sm text-slate-600`)
- Primary button with the next action
- Generous vertical padding (`py-12 sm:py-16`)

Empty state copy should be friendly but not chatty. Example:

```
[icon]
No letter yet for this job.
The agent will draft a tailored letter using your resume.
[Generate cover letter]
```

NOT:
```
"Oops! Looks like there's no letter here yet 😢
Click the magic button below to make one!"
```

---

## What's intentionally deferred to Phase 9 polish

- **Dark mode.** Designed for, but not implemented yet. All colors above
  have dark equivalents we'll wire up later.
- **Internationalization.** English only.
- **Reduced-motion media query.** Respect `prefers-reduced-motion: reduce`
  by skipping the hover-lift transition. (Implementation, not design.)
- **Custom scrollbar styling.** OS default is fine.

---

## Reference implementations

These are the apps to look at when in doubt:

| App                | What to study                                                |
| ------------------ | ------------------------------------------------------------ |
| **Linear**         | Density, keyboard shortcuts, monochrome restraint            |
| **Vercel**         | Card layouts, navigation patterns, subtle hover states       |
| **Stripe**         | Skeleton loaders, hierarchy, professional polish             |
| **Notion**         | Empty states, generous whitespace, soft shadows              |

DON'T look at:
- Bootstrap demos (purple gradients, pill buttons everywhere)
- Material Design site (heavy shadows, "googly" feel)
- Older AdminLTE / dashboard templates (multi-color, busy)
