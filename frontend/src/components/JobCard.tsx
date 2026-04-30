/**
 * JobCard — one row in the Job List.
 *
 * Hover-lifts via the Card component's `interactive` prop. Click the
 * card body to navigate to the detail page; the "Mark applied" / "Mark
 * unapplied" button is intercepted (e.preventDefault) so it doesn't
 * trigger navigation.
 *
 * Visual reference: docs/wireframes/job_list_mockup.html.
 */

import { useNavigate } from "react-router";

import { FitBadge } from "@/components/FitBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatMatchScore, formatPostedAt, formatSalary } from "@/lib/format";
import type { JobSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

interface JobCardProps {
  job: JobSummary;
  onToggleApplied: (job: JobSummary) => void;
  isToggling?: boolean;
}

export function JobCard({ job, onToggleApplied, isToggling = false }: JobCardProps) {
  const navigate = useNavigate();

  const salaryText = formatSalary(job.salary_min, job.salary_max);

  return (
    <Card
      interactive
      onClick={() => navigate(`/jobs/${encodeURIComponent(job.job_id)}`)}
      className={cn(
        "p-5 cursor-pointer",
        job.applied && "opacity-80",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Title + match score + fit */}
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base font-semibold text-slate-900 truncate">
              {job.title}
            </h2>
            <span
              className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-slate-100 text-slate-900 tabular-nums"
              title="Match score — cosine similarity to your resume, scaled 0–100"
            >
              ★ {formatMatchScore(job.match_score)}
            </span>
            <FitBadge fit={job.fit_assessment} />
          </div>

          {/* Company · location · salary */}
          <p className="mt-1 text-sm text-slate-700">
            <span className="font-medium">{job.company}</span>
            <span className="text-slate-400"> · </span>
            {job.location}
            <span className="text-slate-400"> · </span>
            <span className={salaryText === "$—" ? "text-slate-500" : "font-medium tabular-nums"}>
              {salaryText}
            </span>
          </p>

          {/* Publisher · posted */}
          <p className="mt-0.5 text-xs text-slate-500">
            {job.publisher}
            <span className="text-slate-300"> · </span>
            Posted {formatPostedAt(job.posted_at)}
          </p>

          {/* Description preview */}
          {job.description_preview && (
            <p className="mt-3 text-sm text-slate-600 line-clamp-2 leading-relaxed">
              {job.description_preview}
            </p>
          )}
        </div>
      </div>

      {/* Footer: View details + Mark applied */}
      <div className="mt-4 flex items-center justify-between">
        <span className="text-sm font-medium text-indigo-600 hover:text-indigo-700">
          View details →
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            onToggleApplied(job);
          }}
          disabled={isToggling}
        >
          {job.applied ? "Mark unapplied" : "Mark applied"}
        </Button>
      </div>
    </Card>
  );
}


