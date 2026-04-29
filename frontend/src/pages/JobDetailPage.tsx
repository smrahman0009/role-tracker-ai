/**
 * JobDetailPage — single application view. Placeholder; full
 * implementation lands when the API client + TanStack Query are wired up.
 *
 * Final design lives in docs/wireframes/job_detail_mockup.html.
 */

import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router";

import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <Button asChild variant="ghost" size="sm" className="mb-5">
        <Link to="/">
          <ArrowLeft />
          Back to jobs
        </Link>
      </Button>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Job {jobId}</CardTitle>
            <CardDescription>
              Placeholder — JD, generate button, letter viewer, strategy
              panel, refine textarea, and version selector all land in
              the next two commits.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="text-sm text-slate-600">
          Reference: <code className="mx-1 px-1 py-0.5 bg-slate-100 rounded text-xs">docs/wireframes/job_detail_mockup.html</code>
        </CardContent>
      </Card>
    </div>
  );
}
