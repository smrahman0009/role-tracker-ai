# Role Tracker Frontend

React + TypeScript + Vite + Tailwind CSS v4 — the web UI consuming the
FastAPI backend at `../src/role_tracker/api/`.

## Prerequisites

- Node.js 20+ (tested on Node 24)
- The backend running on `http://127.0.0.1:8000` (see top-level
  `scripts/run_api.py`)

## Local development

```bash
# from the project root
cd frontend
npm install         # first time only
npm run dev
```

Visit `http://localhost:5173`. Hot module reload is enabled — edit
files in `src/` and the browser updates without a refresh.

API calls from the frontend hit `/api/*` and are proxied to the
backend at `127.0.0.1:8000`. This avoids CORS configuration during
local dev. See `vite.config.ts` for the proxy rule.

## Production build

```bash
npm run build       # outputs to dist/
npm run preview     # serves dist/ locally for a final smoke test
```

## Layout

```
src/
  App.tsx           # root component (placeholder for now)
  main.tsx          # React entrypoint
  index.css         # Tailwind import + base styles
  pages/            # route pages (Login, JobList, JobDetail) — coming
  components/       # shared UI components — coming
  components/ui/    # shadcn/ui generated components — coming
  lib/              # API client, auth helpers, etc. — coming
  hooks/            # TanStack Query hooks — coming

vite.config.ts      # Vite + Tailwind plugin + path aliases + dev proxy
tsconfig.app.json   # TS for the app (path aliases live here)
tsconfig.node.json  # TS for tooling (Vite config itself)
```

The `@/` alias in imports resolves to `src/` — same convention shadcn/ui
uses. Example: `import { cn } from "@/lib/utils";` (when that helper
lands).

## Phase 6 progress

- [x] Vite + React + TS scaffolding
- [x] Tailwind CSS v4 wired up
- [x] Path alias `@/...` → `src/...`
- [x] Dev proxy for `/api/*` → backend
- [ ] shadcn/ui setup + Button, Card, Input, Tabs, Dialog, Toast components
- [ ] React Router + auth context
- [ ] API client (typed `fetch` wrapper with bearer token)
- [ ] TanStack Query setup
- [ ] Login page
- [ ] Job List page
- [ ] Job Detail page
- [ ] Polish (loading states, error toasts, mobile responsive)

See `../docs/wireframes/README.md` for the page-by-page UX.
