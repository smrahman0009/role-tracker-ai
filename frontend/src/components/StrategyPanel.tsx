/**
 * StrategyPanel — sidebar card showing the agent's commit_to_strategy
 * output: fit assessment + reasoning, narrative angle, and the
 * primary/secondary projects it chose to anchor the letter on.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { FitBadge } from "@/components/FitBadge";
import type { Strategy } from "@/lib/types";

export function StrategyPanel({ strategy }: { strategy: Strategy }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          Strategy
          <FitBadge fit={strategy.fit_assessment} />
        </CardTitle>
      </CardHeader>
      <CardContent className="text-xs text-slate-700 space-y-3">
        <Field label="Fit reasoning" value={strategy.fit_reasoning} />
        <Field label="Narrative angle" value={strategy.narrative_angle} />
        <Field label="Primary project" value={strategy.primary_project} />
        {strategy.secondary_project && (
          <Field
            label="Secondary project"
            value={strategy.secondary_project}
          />
        )}
      </CardContent>
    </Card>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500">
        {label}
      </p>
      <p className="mt-0.5 text-slate-800 leading-relaxed">{value}</p>
    </div>
  );
}
