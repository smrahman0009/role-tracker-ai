/**
 * ManualJobsPage — every job the user has added by URL/paste.
 * Independent of search snapshots; reads from /jobs/manual which
 * filters seen_jobs by source='manual'.
 */

import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { AddManualJobDialog } from "@/components/AddManualJobDialog";
import { JobCard } from "@/components/JobCard";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { toast } from "@/components/ui/Toaster";
import {
  useApplyJob,
  useDeleteManualJob,
  useManualJobs,
  useUnapplyJob,
} from "@/hooks/useJobs";
import type { JobSummary } from "@/lib/types";

export default function ManualJobsPage() {
  const query = useManualJobs();
  const applyMutation = useApplyJob();
  const unapplyMutation = useUnapplyJob();
  const deleteMutation = useDeleteManualJob();
  const [adding, setAdding] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<JobSummary | null>(null);

  const jobs = query.data?.jobs ?? [];

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
      applyMutation.mutate({ jobId: job.job_id }, {
        onSuccess: () => {
          toast.success(`Marked applied: ${job.title}`);
          query.refetch();
        },
        onError: (err) => toast.error(err.message),
      });
    }
  };

  const confirmDelete = () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    deleteMutation.mutate(target.job_id, {
      onSuccess: () => {
        toast.success(`Removed ${target.title}`);
        setDeleteTarget(null);
        query.refetch();
      },
      onError: (err) => {
        toast.error(`Couldn't delete: ${err.message}`);
        setDeleteTarget(null);
      },
    });
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <Button asChild variant="ghost" size="sm" className="mb-4">
        <Link to="/">
          <ArrowLeft />
          Back to search
        </Link>
      </Button>

      <div className="flex items-end justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
            My added jobs
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Postings you've added by URL or paste — useful when JSearch
            doesn't have the job (referrals, direct career pages, etc.).
          </p>
        </div>
        <Button onClick={() => setAdding(true)}>
          <Plus />
          Add a job
        </Button>
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
              Couldn't load
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
            <Plus className="h-6 w-6 text-slate-400 mx-auto" />
            <p className="text-sm font-semibold text-slate-900 mt-3">
              No added jobs yet
            </p>
            <p className="text-xs text-slate-600 mt-1.5 max-w-sm mx-auto">
              When you find a posting elsewhere — a referral, an
              email forward, a smaller board — paste the URL or
              description here and it joins your tracker like any
              other job.
            </p>
            <Button onClick={() => setAdding(true)} className="mt-4">
              <Plus />
              Add a job
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <p className="text-xs text-slate-500 mb-3 tabular-nums">
            {jobs.length} added job{jobs.length === 1 ? "" : "s"}
          </p>
          <div className="flex flex-col gap-3">
            {jobs.map((job) => (
              <div key={job.job_id} className="relative group">
                <JobCard
                  job={job}
                  onToggleApplied={handleToggleApplied}
                  isToggling={
                    applyMutation.isPending || unapplyMutation.isPending
                  }
                />
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteTarget(job);
                  }}
                  className="absolute top-3 right-3 p-1.5 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors focus:outline-none focus:ring-2 focus:ring-rose-500/30"
                  title="Remove this added job"
                  aria-label={`Remove ${job.title}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      <AddManualJobDialog open={adding} onOpenChange={setAdding} />

      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Remove added job?</DialogTitle>
            <DialogDescription>
              This will delete the job, any cover letters generated for
              it, and remove it from My Applications. This can't be
              undone.
            </DialogDescription>
          </DialogHeader>
          {deleteTarget && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700">
              <p className="font-medium text-slate-900">
                {deleteTarget.title}
              </p>
              <p className="text-xs text-slate-500">
                {deleteTarget.company}
                {deleteTarget.location ? ` · ${deleteTarget.location}` : ""}
              </p>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="secondary"
              onClick={() => setDeleteTarget(null)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={confirmDelete}
              disabled={deleteMutation.isPending}
              className="bg-rose-600 hover:bg-rose-700"
            >
              <Trash2 />
              {deleteMutation.isPending ? "Removing…" : "Remove"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
