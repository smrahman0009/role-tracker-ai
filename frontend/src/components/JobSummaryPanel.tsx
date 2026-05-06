/**
 * JobSummaryPanel — Phase 2.5. A 5-6 sentence prose summary of the JD,
 * generated on demand. Sits at the top of the cover-letter workflow
 * (above the match analysis) so the user can read what the role
 * actually is before doing anything else.
 *
 * Per-panel model toggle lets the user A/B between Sonnet and Haiku.
 * Each model's last response is kept in TanStack Query's cache so
 * flipping back is free.
 */

import { useState } from "react";
import { Loader2, FileText } from "lucide-react";

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
  const display = mutation.data && mutation.variables?.model === model
    ? mutation.data
    : cached;

  const isRunning = mutation.isPending;
  const errorMessage = mutation.error?.message;

  const onRun = () => {
    mutation.mutate({ model });
  };

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-slate-900 inline-flex items-center gap-2">
            <FileText className="h-4 w-4 text-slate-500" />
            Role summary
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            What this job is in plain English. Five to six sentences,
            no padding.
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
            variant={display ? "secondary" : "default"}
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
        <p className="mt-3 text-xs text-rose-600">
          Couldn't summarise: {errorMessage}
        </p>
      )}

      {display && (
        <div className="mt-4">
          <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
            {display.summary}
          </p>
          <p className="mt-3 text-[10px] text-slate-400 tabular-nums">
            Summarised by {display.model}
          </p>
        </div>
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
