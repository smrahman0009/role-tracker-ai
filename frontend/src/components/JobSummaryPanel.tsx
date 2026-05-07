/**
 * JobSummaryPanel — Phase 2.5 + 2.7. A three-section JD digest at the
 * top of the cover-letter workflow.
 *
 * The summary endpoint returns three short prose strings:
 *   - role          (sky)      what the job is, seniority, day-to-day
 *   - requirements  (violet)   top 2-3 hard requirements
 *   - context       (stone)    location, comp, who it suits, notable
 *
 * Each renders in its own coloured card so the user can scan
 * independently. Empty fields are skipped (the model is told to
 * leave a field "" if the JD says nothing genuine about it, rather
 * than padding with fluff).
 *
 * Per-panel Sonnet/Haiku toggle so the user can A/B compare cost
 * against quality. Each model's last response is kept in the
 * TanStack Query cache so flipping back to a previously-tried
 * model is free.
 */

import { useState } from "react";
import {
  AlertCircle,
  FileText,
  ListChecks,
  Loader2,
  MapPin,
} from "lucide-react";

import { ModelToggle } from "@/components/ModelToggle";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useJobSummary } from "@/hooks/useJobSummary";
import type { ModelChoice } from "@/lib/types";

interface Props {
  jobId: string;
}

export function JobSummaryPanel({ jobId }: Props) {
  const { mutation, cachedFor } = useJobSummary(jobId);
  const [model, setModel] = useState<ModelChoice>("sonnet");

  const cached = cachedFor(model);
  const display =
    mutation.data && mutation.variables?.model === model
      ? mutation.data
      : cached;

  const isRunning = mutation.isPending;
  const errorMessage = mutation.error?.message;

  const onRun = () => {
    mutation.mutate({ model });
  };

  // Skip empty sections — the prompt is allowed to leave any of them
  // "" when the JD says nothing genuine about that bucket.
  const sections = display
    ? [
        {
          key: "role" as const,
          label: "Role",
          icon: <FileText className="h-3.5 w-3.5" />,
          text: display.role,
          // sky: cool blue, distinct from any analysis-panel colours.
          card: "bg-sky-50 border-sky-200",
          chip: "text-sky-700",
        },
        {
          key: "requirements" as const,
          label: "Requirements",
          icon: <ListChecks className="h-3.5 w-3.5" />,
          text: display.requirements,
          // violet: distinct from amber (gaps) and emerald (strong).
          card: "bg-violet-50 border-violet-200",
          chip: "text-violet-700",
        },
        {
          key: "context" as const,
          label: "Context",
          icon: <MapPin className="h-3.5 w-3.5" />,
          text: display.context,
          // stone: warm neutral, distinct from cool slate.
          card: "bg-stone-50 border-stone-200",
          chip: "text-stone-700",
        },
      ].filter((s) => s.text.trim().length > 0)
    : [];

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-slate-900 inline-flex items-center gap-2">
            <FileText className="h-4 w-4 text-slate-500" />
            Role summary
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Three short sections so you can scan what the role is, what
            it asks for, and any notable context.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ModelToggle
            value={model}
            onChange={setModel}
            disabled={isRunning}
          />
          <Button
            size="sm"
            variant={display ? "secondary" : "primary"}
            onClick={onRun}
            disabled={isRunning}
          >
            {isRunning ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Summarising
              </>
            ) : display ? (
              "Re-run"
            ) : (
              "Summarise"
            )}
          </Button>
        </div>
      </div>

      {errorMessage && (
        <p className="mt-3 text-xs text-rose-600 inline-flex items-center gap-1.5">
          <AlertCircle className="h-3.5 w-3.5" />
          Couldn't summarise: {errorMessage}
        </p>
      )}

      {display && sections.length > 0 && (
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
          {sections.map((s) => (
            <div
              key={s.key}
              className={`rounded-lg border px-3 py-2.5 ${s.card}`}
            >
              <p
                className={`text-[10px] uppercase tracking-wide font-medium inline-flex items-center gap-1 ${s.chip}`}
              >
                {s.icon}
                {s.label}
              </p>
              <p className="mt-1.5 text-xs text-slate-800 leading-relaxed">
                {s.text}
              </p>
            </div>
          ))}
        </div>
      )}

      {display && (
        <p className="mt-3 text-[10px] text-slate-400 tabular-nums">
          Summarised by {display.model}
        </p>
      )}

      {!display && !isRunning && !errorMessage && (
        <p className="mt-4 text-xs text-slate-400 italic">
          Click Summarise to read a short version of the JD before
          composing.
        </p>
      )}
    </Card>
  );
}
