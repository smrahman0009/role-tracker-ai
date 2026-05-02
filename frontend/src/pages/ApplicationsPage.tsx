/**
 * ApplicationsPage — every job the user has marked as applied, with
 * the rich record captured at apply time (applied_at, resume snapshot,
 * letter version used). Sorted by applied_at desc.
 */

import {
  ArrowLeft,
  Building2,
  Calendar,
  CheckCircle2,
  ExternalLink,
  FileText,
  Mail,
  MapPin,
} from "lucide-react";
import { Link, useNavigate } from "react-router";

import { FitBadge } from "@/components/FitBadge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { toast } from "@/components/ui/Toaster";
import { useApplications, useUnapplyJob } from "@/hooks/useJobs";
import { formatMatchScore, formatPostedAt } from "@/lib/format";
import type { ApplicationSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function ApplicationsPage() {
  const query = useApplications();
  const unapplyMutation = useUnapplyJob();

  const handleUnapply = (jobId: string, title: string) => {
    unapplyMutation.mutate(jobId, {
      onSuccess: () => {
        toast.success(`${title} unmarked`);
        query.refetch();
      },
      onError: (err) => toast.error(err.message),
    });
  };

  const apps = query.data?.applications ?? [];

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
          Every job you've marked as applied — most recent first. Each
          row shows the resume and letter version used at apply time.
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
      ) : apps.length === 0 ? (
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
            {apps.length} application{apps.length === 1 ? "" : "s"}
          </p>
          <div className="flex flex-col gap-3">
            {apps.map((app) => (
              <ApplicationCard
                key={app.job.job_id}
                app={app}
                onUnapply={handleUnapply}
                isToggling={unapplyMutation.isPending}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}


function ApplicationCard({
  app,
  onUnapply,
  isToggling,
}: {
  app: ApplicationSummary;
  onUnapply: (jobId: string, title: string) => void;
  isToggling: boolean;
}) {
  const navigate = useNavigate();
  const job = app.job;

  return (
    <Card
      interactive
      onClick={() => navigate(`/jobs/${encodeURIComponent(job.job_id)}`)}
      className="p-5 cursor-pointer"
    >
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base font-semibold text-slate-900 truncate">
              {job.title}
            </h2>
            <span
              className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-slate-100 text-slate-900 tabular-nums"
              title="Match score (cosine similarity to your resume, 0–100)"
            >
              ★ {formatMatchScore(job.match_score)}
            </span>
            <FitBadge fit={job.fit_assessment} />
          </div>

          <p className="mt-1 text-sm text-slate-700 inline-flex items-center gap-3 flex-wrap">
            <span className="inline-flex items-center gap-1">
              <Building2 className="h-3 w-3 text-slate-400" />
              {job.company}
            </span>
            <span className="inline-flex items-center gap-1 text-slate-500">
              <MapPin className="h-3 w-3 text-slate-400" />
              {job.location}
            </span>
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            onUnapply(job.job_id, job.title);
          }}
          disabled={isToggling}
          title="Move back to Unapplied"
        >
          Mark unapplied
        </Button>
      </div>

      {/* Audit row — applied / posted dates, resume, letter */}
      <div className="mt-4 pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
        <Field
          icon={<Calendar className="h-3 w-3" />}
          label="Applied"
          value={app.applied_at ? formatPostedAt(app.applied_at) : "—"}
        />
        <Field
          icon={<Calendar className="h-3 w-3" />}
          label="Posted"
          value={job.posted_at ? formatPostedAt(job.posted_at) : "—"}
        />
        <Field
          icon={<FileText className="h-3 w-3" />}
          label="Resume"
          value={
            app.resume_filename ? (
              <span className="inline-flex items-center gap-1.5">
                <span
                  className={cn(
                    "truncate",
                    app.resume_replaced_since && "text-slate-400 line-through",
                  )}
                  title={app.resume_filename}
                >
                  {app.resume_filename}
                </span>
                {app.resume_replaced_since && (
                  <span
                    className="text-[10px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-1 py-px"
                    title="You've uploaded a different resume since applying"
                  >
                    now replaced
                  </span>
                )}
              </span>
            ) : (
              "—"
            )
          }
        />
        <Field
          icon={<Mail className="h-3 w-3" />}
          label="Letter"
          value={
            app.letter_version_used != null ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/jobs/${encodeURIComponent(job.job_id)}`);
                }}
                className="inline-flex items-center gap-1 text-indigo-700 hover:underline"
              >
                v{app.letter_version_used}
                <ExternalLink className="h-3 w-3" />
              </button>
            ) : (
              "—"
            )
          }
        />
      </div>
    </Card>
  );
}


function Field({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 min-w-0">
      <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide font-medium text-slate-500 w-16 shrink-0">
        {icon}
        {label}
      </span>
      <span className="text-slate-800 truncate">{value}</span>
    </div>
  );
}
