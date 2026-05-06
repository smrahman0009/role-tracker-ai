/**
 * CoverLetterAnalysisPanel — Phase 1 of the interactive cover letter
 * flow.
 *
 * Renders the four bullet lists returned by
 * POST /cover-letter/analysis (Strong, Gaps, Partial, Excitement
 * hooks) once the user clicks "Run analysis". Not auto-fetched on
 * mount because the call costs money. The TanStack Query cache
 * preserves the result for the rest of the session.
 *
 * Layout: a single Card with four sections separated by a faint
 * divider. Strong is green-tinted, Gaps amber, Partial slate,
 * Excitement indigo. No icons inside the bullets, just the text,
 * to keep it scannable.
 */

import {
  Loader2,
  ListChecks,
  AlertTriangle,
  CircleDashed,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  useCoverLetterAnalysis,
  useRunCoverLetterAnalysis,
} from "@/hooks/useCoverLetterAnalysis";

interface Props {
  jobId: string;
}

export function CoverLetterAnalysisPanel({ jobId }: Props) {
  const cached = useCoverLetterAnalysis(jobId);
  const run = useRunCoverLetterAnalysis(jobId);

  // Treat any cached value (even one with all-empty lists) as "run".
  const data = run.data ?? cached.data;
  const isRunning = run.isPending;
  const errorMessage = run.error?.message;

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Match analysis
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            How your resume lines up with this job. Drives the cover-letter
            options below.
          </p>
        </div>
        <Button
          size="sm"
          variant={data ? "secondary" : "default"}
          onClick={() => run.mutate()}
          disabled={isRunning}
        >
          {isRunning ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Analyzing
            </>
          ) : data ? (
            "Re-run"
          ) : (
            "Run analysis"
          )}
        </Button>
      </div>

      {errorMessage && (
        <p className="mt-3 text-xs text-rose-600">
          Couldn't run analysis: {errorMessage}
        </p>
      )}

      {data && (
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <BulletList
            title="Strong matches"
            tone="strong"
            icon={<ListChecks className="h-3.5 w-3.5" />}
            items={data.strong}
          />
          <BulletList
            title="Gaps"
            tone="gap"
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
            items={data.gaps}
          />
          <BulletList
            title="Partial matches"
            tone="partial"
            icon={<CircleDashed className="h-3.5 w-3.5" />}
            items={data.partial}
          />
          <BulletList
            title="What might excite you"
            tone="excitement"
            icon={<Sparkles className="h-3.5 w-3.5" />}
            items={data.excitement_hooks}
          />
        </div>
      )}

      {data && (
        <p className="mt-4 text-[10px] text-slate-400 tabular-nums">
          Analysis by {data.model}
        </p>
      )}
    </Card>
  );
}

type Tone = "strong" | "gap" | "partial" | "excitement";

const TONE_STYLES: Record<Tone, { header: string; bullet: string }> = {
  strong: {
    header: "text-emerald-700",
    bullet: "text-slate-700",
  },
  gap: {
    header: "text-amber-700",
    bullet: "text-slate-700",
  },
  partial: {
    header: "text-slate-700",
    bullet: "text-slate-700",
  },
  excitement: {
    header: "text-indigo-700",
    bullet: "text-slate-700",
  },
};

function BulletList({
  title,
  tone,
  icon,
  items,
}: {
  title: string;
  tone: Tone;
  icon: React.ReactNode;
  items: string[];
}) {
  const styles = TONE_STYLES[tone];

  return (
    <div>
      <p
        className={`text-[11px] uppercase tracking-wide font-medium inline-flex items-center gap-1 ${styles.header}`}
      >
        {icon}
        {title}
        <span className="text-slate-400 font-normal tabular-nums">
          {items.length}
        </span>
      </p>
      {items.length === 0 ? (
        <p className="mt-1.5 text-xs text-slate-400">None.</p>
      ) : (
        <ul className="mt-1.5 space-y-1">
          {items.map((item, i) => (
            <li
              key={i}
              className={`text-xs leading-relaxed ${styles.bullet} pl-3 relative before:absolute before:left-0 before:top-2 before:w-1 before:h-1 before:rounded-full before:bg-slate-400`}
            >
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
