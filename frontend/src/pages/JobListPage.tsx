/**
 * JobListPage — home page. Placeholder; full implementation lands when
 * the API client + TanStack Query are wired up.
 *
 * Final design lives in docs/wireframes/job_list_mockup.html.
 */

import { Link } from "react-router";

import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";

export default function JobListPage() {
  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
            Job matches
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Coming next: filter chips, ranked cards, refresh button.
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Placeholder</CardTitle>
            <CardDescription>
              The real Job List page wires up TanStack Query against
              GET /users/{`{userId}`}/jobs in the next commit.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="text-sm text-slate-600 space-y-3">
          <p>
            Reference: open
            <code className="mx-1 px-1 py-0.5 bg-slate-100 rounded text-xs">
              docs/wireframes/job_list_mockup.html
            </code>
            in your browser to see the target visual.
          </p>
          <div className="flex gap-2 pt-2">
            <Button asChild variant="secondary">
              <Link to="/jobs/example-id">Open job detail (placeholder)</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/settings">Open settings</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
