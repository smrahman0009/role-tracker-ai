/**
 * App — Phase 6 placeholder.
 *
 * No router yet. No real pages yet. Just a single welcome screen styled
 * with Tailwind to confirm the toolchain is wired correctly. Real pages
 * (Login, Job List, Job Detail) land in subsequent commits.
 */
export default function App() {
  return (
    <main className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="max-w-xl w-full bg-white rounded-2xl shadow-sm border border-slate-200 p-10 text-center">
        <h1 className="text-3xl font-semibold text-slate-900 tracking-tight">
          Role Tracker
        </h1>
        <p className="mt-2 text-sm uppercase tracking-wider text-slate-500">
          Frontend · Phase 6
        </p>

        <div className="mt-8 text-left text-slate-700 leading-relaxed">
          <p>
            Vite + React + TypeScript + Tailwind v4 are wired up. The
            development server proxies <code className="px-1 py-0.5 bg-slate-100 rounded text-sm">/api/*</code> to
            the FastAPI backend at <code className="px-1 py-0.5 bg-slate-100 rounded text-sm">127.0.0.1:8000</code>.
          </p>
          <p className="mt-4">
            Next commit replaces this placeholder with the Login page,
            adds router and shadcn/ui, and starts hooking up real
            backend calls.
          </p>
        </div>

        <a
          href="http://127.0.0.1:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block mt-8 px-5 py-2.5 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
        >
          Open API docs ↗
        </a>
      </div>
    </main>
  );
}
