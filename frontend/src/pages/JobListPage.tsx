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
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { FilterChips } from "@/components/FilterChips";
import { JobCard } from "@/components/JobCard";
import { formatDateTime } from "@/lib/format";
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
import type {
  EmploymentType,
  JobFilter,
  JobListFilters,
  JobSummary,
} from "@/lib/types";

export default function JobListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = (searchParams.get("filter") as JobFilter) ?? "unapplied";
  const chipFilters = useMemo(() => parseFilters(searchParams), [searchParams]);

  // Fetch jobs with chip filters applied server-side (filter=all so we
  // can partition client-side for the tab counts). Tab counts then
  // correctly reflect the active chip filters.
  const allJobsQuery = useJobs({ ...chipFilters, filter: "all" });
  const allJobs = allJobsQuery.data?.jobs ?? [];
  const totalUnfiltered = allJobsQuery.data?.total_unfiltered ?? 0;
  const hiddenByFilters = allJobsQuery.data?.hidden_by_filters ?? 0;
  const visibleJobs = allJobs.filter((j) =>
    filter === "applied" ? j.applied : filter === "unapplied" ? !j.applied : true,
  );

  const counts = {
    all: allJobs.length,
    unapplied: allJobs.filter((j) => !j.applied).length,
    applied: allJobs.filter((j) => j.applied).length,
  };

  const locationOptions = useMemo(() => {
    const set = new Set<string>();
    for (const j of allJobs) if (j.location) set.add(j.location);
    return Array.from(set).sort();
  }, [allJobs]);

  const setFilter = (next: JobFilter) => {
    const sp = new URLSearchParams(searchParams);
    if (next === "unapplied") sp.delete("filter");
    else sp.set("filter", next);
    setSearchParams(sp, { replace: true });
  };

  const setChipFilters = (next: JobListFilters) => {
    const sp = new URLSearchParams();
    if (filter !== "unapplied") sp.set("filter", filter);
    writeFilters(sp, next);
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
      const d = refreshStatus.data;
      const kept = d?.jobs_added ?? 0;
      const seen = d?.candidates_seen ?? 0;
      const queries = d?.queries_run ?? 0;
      const detail =
        seen > 0 && queries > 0
          ? ` · kept top ${kept} of ${seen} candidates from ${queries} ${queries === 1 ? "search" : "searches"}`
          : "";
      toast.success(`Refresh complete${detail}`);
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
              {formatDateTime(allJobsQuery.data?.last_refreshed_at)}
            </span>
          </p>
          <PipelineSummary data={allJobsQuery.data} />
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

      {/* Filter chips */}
      <div className="mb-4">
        <FilterChips
          filters={chipFilters}
          onChange={setChipFilters}
          locationOptions={locationOptions}
        />
        {hiddenByFilters > 0 && (
          <p className="mt-2 text-xs text-slate-500">
            Showing {allJobs.length} of {totalUnfiltered} ·{" "}
            <span className="text-slate-700">{hiddenByFilters} hidden by filters</span>
          </p>
        )}
      </div>

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


function PipelineSummary({
  data,
}: {
  data: import("@/lib/types").JobListResponse | undefined;
}) {
  if (!data || !data.last_refreshed_at) return null;
  const { candidates_seen, queries_run, top_n_cap, total_unfiltered } = data;
  if (candidates_seen <= 0 || queries_run <= 0) return null;
  const cap = top_n_cap || total_unfiltered;
  const tooltip =
    "JSearch returns up to 50 jobs per saved search. We embed each JD plus your resume and keep the top matches by cosine similarity, then apply your hidden lists. The cap is your 'Max jobs to keep per refresh' setting.";
  return (
    <p
      className="text-xs text-slate-500 mt-0.5"
      title={tooltip}
    >
      Top {Math.min(cap, total_unfiltered)} of {candidates_seen} candidates ·
      ranked by resume match across {queries_run}{" "}
      {queries_run === 1 ? "search" : "searches"}
    </p>
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


const EMPLOYMENT_VALUES: EmploymentType[] = [
  "FULLTIME",
  "PARTTIME",
  "CONTRACTOR",
  "INTERN",
];

function parseFilters(sp: URLSearchParams): JobListFilters {
  const csv = (k: string): string[] | undefined => {
    const raw = sp.get(k);
    if (!raw) return undefined;
    const parts = raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    return parts.length ? parts : undefined;
  };
  const num = (k: string): number | undefined => {
    const raw = sp.get(k);
    if (raw == null) return undefined;
    const n = Number(raw);
    return Number.isFinite(n) ? n : undefined;
  };
  const employmentRaw = csv("employment_types");
  const employment_types = employmentRaw?.filter((v): v is EmploymentType =>
    (EMPLOYMENT_VALUES as string[]).includes(v),
  );
  return {
    type: csv("type"),
    location: csv("location"),
    salary_min: num("salary_min"),
    hide_no_salary: sp.get("hide_no_salary") === "1" ? true : undefined,
    employment_types: employment_types?.length ? employment_types : undefined,
    posted_within_days: num("posted_within_days"),
  };
}

function writeFilters(sp: URLSearchParams, f: JobListFilters): void {
  if (f.type?.length) sp.set("type", f.type.join(","));
  if (f.location?.length) sp.set("location", f.location.join(","));
  if (f.salary_min != null) sp.set("salary_min", String(f.salary_min));
  if (f.hide_no_salary) sp.set("hide_no_salary", "1");
  if (f.employment_types?.length) sp.set("employment_types", f.employment_types.join(","));
  if (f.posted_within_days != null)
    sp.set("posted_within_days", String(f.posted_within_days));
}

