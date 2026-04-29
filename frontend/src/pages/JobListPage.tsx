/**
 * JobListPage — the home page.
 *
 * Tabs (Unapplied / All / Applied) with counts, a Refresh button that
 * kicks off a background refresh and polls until done, and a list of
 * JobCards that route to /jobs/:jobId on click.
 *
 * Filter chips (job type, location, salary, etc.) ship in the next
 * commit — this commit gets the basic list working first.
 */

import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { JobCard } from "@/components/JobCard";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { toast } from "@/components/ui/Toaster";
import {
  useApplyJob,
  useJobs,
  useRefreshJobs,
  useRefreshStatus,
  useUnapplyJob,
} from "@/hooks/useJobs";
import type { JobFilter, JobSummary } from "@/lib/types";

export default function JobListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = (searchParams.get("filter") as JobFilter) ?? "unapplied";

  // We render Unapplied/All/Applied tabs from a single jobs list so that
  // the counts on each tab are accurate (otherwise we'd need three fetches).
  // Fetch all jobs (filter=all), then partition client-side for the tab counts.
  // The active tab's filtered list is the one we render.
  const allJobsQuery = useJobs({ filter: "all" });
  const allJobs = allJobsQuery.data?.jobs ?? [];
  const visibleJobs = allJobs.filter((j) =>
    filter === "applied" ? j.applied : filter === "unapplied" ? !j.applied : true,
  );

  const counts = {
    all: allJobs.length,
    unapplied: allJobs.filter((j) => !j.applied).length,
    applied: allJobs.filter((j) => j.applied).length,
  };

  const setFilter = (next: JobFilter) => {
    const sp = new URLSearchParams(searchParams);
    if (next === "unapplied") sp.delete("filter");
    else sp.set("filter", next);
    setSearchParams(sp, { replace: true });
  };

  // Refresh flow.
  const refreshMutation = useRefreshJobs();
  const [activeRefreshId, setActiveRefreshId] = useState<string | null>(null);
  const refreshStatus = useRefreshStatus(activeRefreshId);

  const handleRefresh = () => {
    refreshMutation.mutate(undefined, {
      onSuccess: (data) => {
        setActiveRefreshId(data.refresh_id);
      },
      onError: (err) => toast.error(`Refresh failed: ${err.message}`),
    });
  };

  // When the polled refresh completes, invalidate jobs + clear the polling.
  useEffect(() => {
    const status = refreshStatus.data?.status;
    if (status === "done") {
      toast.success(`Refreshed · ${refreshStatus.data?.jobs_added ?? 0} jobs ranked`);
      allJobsQuery.refetch();
      setActiveRefreshId(null);
    } else if (status === "failed") {
      toast.error(`Refresh failed: ${refreshStatus.data?.error ?? "unknown"}`);
      setActiveRefreshId(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshStatus.data?.status]);

  const isRefreshing =
    refreshMutation.isPending ||
    (refreshStatus.data?.status === "pending" ||
      refreshStatus.data?.status === "running");

  // Apply / unapply.
  const applyMutation = useApplyJob();
  const unapplyMutation = useUnapplyJob();

  const handleToggleApplied = (job: JobSummary) => {
    if (job.applied) {
      unapplyMutation.mutate(job.job_id, {
        onSuccess: () => toast.success(`${job.title} unmarked`),
        onError: (err) => toast.error(err.message),
      });
    } else {
      applyMutation.mutate(job.job_id, {
        onSuccess: () => toast.success(`Marked applied: ${job.title}`),
        onError: (err) => toast.error(err.message),
      });
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Title row */}
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
            Job matches
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Last refreshed{" "}
            <span className="font-medium text-slate-700">
              {formatRefreshedAt(allJobsQuery.data?.last_refreshed_at)}
            </span>
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={handleRefresh}
          disabled={isRefreshing}
        >
          <RefreshCw className={isRefreshing ? "animate-spin" : ""} />
          {isRefreshing ? "Refreshing…" : "Refresh jobs"}
        </Button>
      </div>

      {/* Refresh banner */}
      {isRefreshing && <RefreshBanner status={refreshStatus.data?.status} />}

      {/* Tabs */}
      <Tabs value={filter} onValueChange={(v) => setFilter(v as JobFilter)}>
        <TabsList>
          <TabsTrigger value="unapplied">
            Unapplied{" "}
            <span className="ml-1 text-slate-400 font-normal">{counts.unapplied}</span>
          </TabsTrigger>
          <TabsTrigger value="all">
            All <span className="ml-1 text-slate-400 font-normal">{counts.all}</span>
          </TabsTrigger>
          <TabsTrigger value="applied">
            Applied <span className="ml-1 text-slate-400 font-normal">{counts.applied}</span>
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {/* List */}
      <div className="mt-5">
        {allJobsQuery.isLoading ? (
          <LoadingState />
        ) : allJobsQuery.isError ? (
          <ErrorState message={allJobsQuery.error.message} onRetry={() => allJobsQuery.refetch()} />
        ) : visibleJobs.length === 0 ? (
          <EmptyState filter={filter} totalAll={counts.all} onRefresh={handleRefresh} />
        ) : (
          <div className="flex flex-col gap-3">
            {visibleJobs.map((job) => (
              <JobCard
                key={job.job_id}
                job={job}
                onToggleApplied={handleToggleApplied}
                isToggling={
                  applyMutation.isPending || unapplyMutation.isPending
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


function RefreshBanner({ status }: { status?: string }) {
  return (
    <Card className="mb-5 border-indigo-200 bg-indigo-50">
      <CardContent className="py-3 px-5 flex items-center gap-3">
        <RefreshCw className="h-4 w-4 text-indigo-600 animate-spin" />
        <div className="flex-1">
          <p className="text-sm font-medium text-indigo-900">
            {status === "running"
              ? "Searching, filtering, and ranking jobs…"
              : "Starting refresh…"}
          </p>
          <p className="text-xs text-indigo-700 mt-0.5">
            This usually takes 60-90 seconds.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}


function LoadingState() {
  return (
    <div className="flex flex-col gap-3">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="p-5 animate-pulse">
          <div className="h-4 bg-slate-200 rounded w-1/2 mb-3" />
          <div className="h-3 bg-slate-200 rounded w-1/3 mb-2" />
          <div className="h-3 bg-slate-100 rounded w-3/4" />
        </Card>
      ))}
    </div>
  );
}


function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="py-12 px-6 text-center">
      <p className="text-sm font-semibold text-slate-900">Couldn't load jobs</p>
      <p className="text-xs text-slate-600 mt-1.5">{message}</p>
      <Button onClick={onRetry} className="mt-4">
        Try again
      </Button>
    </Card>
  );
}


function EmptyState({
  filter,
  totalAll,
  onRefresh,
}: {
  filter: JobFilter;
  totalAll: number;
  onRefresh: () => void;
}) {
  if (totalAll === 0) {
    return (
      <Card className="py-16 px-6 text-center">
        <p className="text-sm font-semibold text-slate-900">No jobs cached yet</p>
        <p className="text-xs text-slate-600 mt-1.5 max-w-sm mx-auto">
          Click "Refresh jobs" to fetch matches from your saved searches. Make
          sure you've uploaded a resume and saved at least one search in
          Settings first.
        </p>
        <Button onClick={onRefresh} className="mt-4">
          <RefreshCw />
          Refresh jobs
        </Button>
      </Card>
    );
  }
  const label =
    filter === "applied"
      ? "Nothing marked applied yet."
      : filter === "unapplied"
        ? "All jobs are marked applied."
        : "No jobs match.";
  return (
    <Card className="py-12 px-6 text-center">
      <p className="text-sm text-slate-600">{label}</p>
    </Card>
  );
}


function formatRefreshedAt(iso: string | null | undefined): string {
  if (!iso) return "never";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      day: "numeric",
      month: "short",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
