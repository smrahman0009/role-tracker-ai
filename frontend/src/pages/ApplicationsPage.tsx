/**
 * ApplicationsPage — every job the user has ever marked as applied,
 * across all searches. Reads from /jobs/applications, which crosses
 * seen_jobs (the long-lived index) with the applied_store.
 *
 * Useful because the home page only shows the *current* search's
 * results — applications from past searches would otherwise be
 * unreachable until they happen to surface again.
 */

import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { Link } from "react-router";

import { JobCard } from "@/components/JobCard";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { toast } from "@/components/ui/Toaster";
import { useAuth } from "@/auth/AuthContext";
import { useApplyJob, useUnapplyJob } from "@/hooks/useJobs";
import { api } from "@/lib/api";
import type { JobListResponse, JobSummary } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";

function useApplications() {
  const { userId } = useAuth();
  return useQuery<JobListResponse>({
    queryKey: ["applications", userId],
    queryFn: () =>
      api.get<JobListResponse>(`/users/${userId}/jobs/applications`),
    enabled: Boolean(userId),
  });
}

export default function ApplicationsPage() {
  const query = useApplications();
  const applyMutation = useApplyJob();
  const unapplyMutation = useUnapplyJob();

  const handleToggleApplied = (job: JobSummary) => {
    if (job.applied) {
      unapplyMutation.mutate(job.job_id, {
        onSuccess: () => {
          toast.success(`${job.title} unmarked`);
          query.refetch();
        },
        onError: (err) => toast.error(err.message),
      });
    } else {
      applyMutation.mutate(job.job_id, {
        onSuccess: () => {
          toast.success(`Marked applied: ${job.title}`);
          query.refetch();
        },
        onError: (err) => toast.error(err.message),
      });
    }
  };

  const jobs = query.data?.jobs ?? [];

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <Button asChild variant="ghost" size="sm" className="mb-4">
        <Link to="/">
          <ArrowLeft />
          Back to search
        </Link>
      </Button>

      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
          My applications
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Every job you've marked as applied — including ones from past
          searches.
        </p>
      </div>

      {query.isLoading ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-slate-500">
            Loading…
          </CardContent>
        </Card>
      ) : query.isError ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-sm font-semibold text-slate-900">
              Couldn't load applications
            </p>
            <p className="text-xs text-slate-600 mt-1">
              {query.error.message}
            </p>
            <Button onClick={() => query.refetch()} className="mt-4">
              Try again
            </Button>
          </CardContent>
        </Card>
      ) : jobs.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <CheckCircle2 className="h-6 w-6 text-slate-400 mx-auto" />
            <p className="text-sm font-semibold text-slate-900 mt-3">
              No applications yet
            </p>
            <p className="text-xs text-slate-600 mt-1.5 max-w-sm mx-auto">
              Search for jobs on the home page and click "Mark applied" on
              any you've applied to. They'll appear here.
            </p>
            <Button asChild className="mt-4">
              <Link to="/">Go to search</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <p className="text-xs text-slate-500 mb-3 tabular-nums">
            {jobs.length} application{jobs.length === 1 ? "" : "s"}
          </p>
          <div className="flex flex-col gap-3">
            {jobs.map((job) => (
              <JobCard
                key={job.job_id}
                job={job}
                onToggleApplied={handleToggleApplied}
                isToggling={applyMutation.isPending || unapplyMutation.isPending}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
