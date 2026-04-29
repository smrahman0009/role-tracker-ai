/**
 * NotFoundPage — catches unknown routes. Friendly empty state, not an
 * error page. Most users get here by typo or stale bookmark.
 */

import { Link } from "react-router";

import { Button } from "@/components/ui/Button";

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="max-w-sm text-center space-y-3">
        <p className="text-xs uppercase tracking-wider text-slate-400 font-medium">
          404
        </p>
        <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
          Page not found
        </h1>
        <p className="text-sm text-slate-600">
          The page you were looking for doesn't exist or was moved.
        </p>
        <Button asChild className="mt-4">
          <Link to="/">Back to jobs</Link>
        </Button>
      </div>
    </div>
  );
}
