/**
 * Home page — search-first.
 *
 * Three blocks: ResumeCard → SearchForm → Results. Submitting the form
 * fires POST /jobs/search; we poll until done, then re-fetch /jobs to
 * render the snapshot the search wrote. The applied/unapplied tabs
 * still filter the result list because users may have applied to some
 * of these jobs from earlier searches.
 */

import { Loader2, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { JobCard } from "@/components/JobCard";
import { ResumeCard } from "@/components/ResumeCard";
import { SearchForm } from "@/components/SearchForm";
import { Card, CardContent } from "@/components/ui/Card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { toast } from "@/components/ui/Toaster";
import {
  useApplyJob,
  useJobs,
  useSearchJobs,
  useSearchStatus,
  useUnapplyJob,
} from "@/hooks/useJobs";
import { useResume } from "@/hooks/useResume";
import { formatDateTime } from "@/lib/format";
import type {
  JobFilter,
  JobSummary,
  SearchJobsRequest,
} from "@/lib/types";

const LAST_SEARCH_KEY = "role-tracker.last-search";

export default function JobListPage() {
  const resumeQuery = useResume();
  const hasResume = !!resumeQuery.data;

  // The search spec we submitted most recently. Stored in localStorage so
  // the form is pre-filled on return, matching plot-hole #3 in the plan.
  const [lastSpec, setLastSpec] = useState<SearchJobsRequest | null>(() =>
    loadLastSpec(),
  );

  // Active search task — null when idle.
  const [activeSearchId, setActiveSearchId] = useState<string | null>(null);
  const searchStatus = useSearchStatus(activeSearchId);
  const isSearching =
    activeSearchId != null &&
    searchStatus.data?.status !== "done" &&
    searchStatus.data?.status !== "failed";

  // Tab state — applied / unapplied / all over the result list.
  const [filter, setFilter] = useState<JobFilter>("unapplied");

  // Load the snapshot that the most recent search wrote.
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

  // Search lifecycle.
  const searchMutation = useSearchJobs();

  const submitSearch = (spec: SearchJobsRequest) => {
    setLastSpec(spec);
    saveLastSpec(spec);
    searchMutation.mutate(spec, {
      onSuccess: (d) => setActiveSearchId(d.search_id),
      onError: (err) => toast.error(`Search failed: ${err.message}`),
    });
  };

  // When the polled search completes, refetch the job list and clear polling.
  useEffect(() => {
    if (!activeSearchId) return;
    const status = searchStatus.data?.status;
    if (status === "done") {
      const d = searchStatus.data;
      const kept = d?.jobs_added ?? 0;
      const seen = d?.candidates_seen ?? 0;
      const detail =
        seen > 0 ? ` · kept top ${kept} of ${seen} candidates` : "";
      toast.success(`Search complete${detail}`);
      allJobsQuery.refetch();
      setActiveSearchId(null);
    } else if (status === "failed") {
      toast.error(`Search failed: ${searchStatus.data?.error ?? "unknown"}`);
      setActiveSearchId(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchStatus.data?.status]);

  // Apply / unapply on cards.
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

  const lastRefreshedAt = allJobsQuery.data?.last_refreshed_at;

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
          Find a job
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Live search ranked against your resume. Saved daily searches live
          in Settings.
        </p>
      </div>

      <ResumeCard onResumeChange={() => resumeQuery.refetch()} />

      <SearchForm
        initial={lastSpec}
        disabled={!hasResume}
        disabledReason={
          hasResume ? undefined : "Upload a resume above to enable search."
        }
        isSearching={isSearching || searchMutation.isPending}
        onSubmit={submitSearch}
      />

      {/* Results section */}
      {isSearching ? (
        <SearchBanner status={searchStatus.data?.status} />
      ) : allJobs.length === 0 ? (
        <EmptyResults hasSearched={lastSpec != null} />
      ) : (
        <div className="space-y-4 pt-2">
          <ResultsHeader
            spec={lastSpec}
            data={allJobsQuery.data}
            lastRefreshedAt={lastRefreshedAt}
          />

          <Tabs value={filter} onValueChange={(v) => setFilter(v as JobFilter)}>
            <TabsList>
              <TabsTrigger value="unapplied">
                Unapplied{" "}
                <span className="ml-1 text-slate-400 font-normal">
                  {counts.unapplied}
                </span>
              </TabsTrigger>
              <TabsTrigger value="all">
                All{" "}
                <span className="ml-1 text-slate-400 font-normal">
                  {counts.all}
                </span>
              </TabsTrigger>
              <TabsTrigger value="applied">
                Applied{" "}
                <span className="ml-1 text-slate-400 font-normal">
                  {counts.applied}
                </span>
              </TabsTrigger>
            </TabsList>
          </Tabs>

          {filter === "unapplied" && counts.applied > 0 && (
            <p className="text-[11px] text-slate-500 -mt-2">
              {counts.applied} job{counts.applied === 1 ? "" : "s"} you've
              already applied to are hidden in this tab.
            </p>
          )}

          {visibleJobs.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-sm text-slate-600">
                {filter === "applied"
                  ? "Nothing marked applied yet."
                  : "All jobs are marked applied."}
              </CardContent>
            </Card>
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
      )}
    </div>
  );
}

// ---------- pieces ----------

function SearchBanner({ status }: { status?: string }) {
  return (
    <Card className="border-indigo-200 bg-indigo-50">
      <CardContent className="py-3 px-5 flex items-center gap-3">
        <Loader2 className="h-4 w-4 text-indigo-600 animate-spin" />
        <div className="flex-1">
          <p className="text-sm font-medium text-indigo-900">
            {status === "running"
              ? "Searching, filtering, and ranking jobs…"
              : "Starting search…"}
          </p>
          <p className="text-xs text-indigo-700 mt-0.5">
            Usually 30–60 seconds.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyResults({ hasSearched }: { hasSearched: boolean }) {
  return (
    <Card>
      <CardContent className="py-12 text-center">
        <Search className="h-6 w-6 text-slate-400 mx-auto" />
        <p className="text-sm font-semibold text-slate-900 mt-3">
          {hasSearched ? "No jobs matched that search" : "Search to find jobs"}
        </p>
        <p className="text-xs text-slate-600 mt-1.5 max-w-sm mx-auto">
          {hasSearched
            ? "Try broader terms, a wider location, or different filters."
            : "Fill in what you're looking for and where, then hit Find jobs. We'll fetch live results and rank them by your resume."}
        </p>
      </CardContent>
    </Card>
  );
}

function ResultsHeader({
  spec,
  data,
  lastRefreshedAt,
}: {
  spec: SearchJobsRequest | null;
  data: import("@/lib/types").JobListResponse | undefined;
  lastRefreshedAt: string | null | undefined;
}) {
  if (!data) return null;
  const { candidates_seen, queries_run, top_n_cap, total_unfiltered } = data;
  const showStats = candidates_seen > 0 && queries_run > 0;
  const cap = top_n_cap || total_unfiltered;
  return (
    <div>
      <p className="text-sm text-slate-700">
        {spec ? (
          <>
            <span className="font-medium">{spec.what}</span>
            <span className="text-slate-400 mx-1.5">in</span>
            <span className="font-medium">{spec.where}</span>
          </>
        ) : (
          "Latest results"
        )}
      </p>
      <p className="text-[11px] text-slate-500 mt-0.5">
        Last searched{" "}
        <span className="text-slate-700 font-medium">
          {formatDateTime(lastRefreshedAt)}
        </span>
        {showStats && (
          <>
            {" · "}
            Top {Math.min(cap, total_unfiltered)} of {candidates_seen}{" "}
            candidates · ranked by resume match
          </>
        )}
      </p>
    </div>
  );
}

// ---------- localStorage helpers ----------

function loadLastSpec(): SearchJobsRequest | null {
  try {
    const raw = localStorage.getItem(LAST_SEARCH_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SearchJobsRequest;
    if (!parsed.what || !parsed.where) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveLastSpec(spec: SearchJobsRequest): void {
  try {
    localStorage.setItem(LAST_SEARCH_KEY, JSON.stringify(spec));
  } catch {
    // localStorage can be disabled / full — ignore.
  }
}
