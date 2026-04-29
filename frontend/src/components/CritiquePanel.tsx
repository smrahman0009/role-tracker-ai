/**
 * CritiquePanel — Haiku's 110-point scorecard for the current letter.
 * Shows total + verdict, per-category bars, failed thresholds, and notes.
 */

import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { CritiqueScore, Verdict } from "@/lib/types";

const VERDICT_STYLE: Record<
  Verdict,
  { label: string; cls: string; Icon: typeof CheckCircle2 }
> = {
  approved: {
    label: "Approved",
    cls: "bg-emerald-50 text-emerald-800 border-emerald-200",
    Icon: CheckCircle2,
  },
  minor_revision: {
    label: "Minor revision",
    cls: "bg-amber-50 text-amber-800 border-amber-200",
    Icon: AlertTriangle,
  },
  rewrite_required: {
    label: "Rewrite required",
    cls: "bg-rose-50 text-rose-800 border-rose-200",
    Icon: XCircle,
  },
};

export function CritiquePanel({ critique }: { critique: CritiqueScore }) {
  const v = VERDICT_STYLE[critique.verdict];
  const categories = Object.entries(critique.category_scores);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Critique</CardTitle>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5",
            "text-[11px] font-medium",
            v.cls,
          )}
        >
          <v.Icon className="h-3 w-3" />
          {v.label}
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-semibold text-slate-900 tabular-nums">
              {critique.total}
            </span>
            <span className="text-xs text-slate-500">/ 110</span>
          </div>
        </div>

        {categories.length > 0 && (
          <div className="space-y-2">
            {categories.map(([name, score]) => (
              <CategoryBar key={name} name={name} score={score} />
            ))}
          </div>
        )}

        {critique.failed_thresholds.length > 0 && (
          <div>
            <p className="text-[10px] uppercase tracking-wide font-medium text-rose-700">
              Failed thresholds
            </p>
            <ul className="mt-1 space-y-0.5 text-xs text-rose-800 list-disc pl-4">
              {critique.failed_thresholds.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
        )}

        {critique.notes && (
          <div>
            <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500">
              Notes
            </p>
            <p className="mt-1 text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">
              {critique.notes}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Max points per critique category, mirroring the backend rubric in
// src/role_tracker/cover_letter/critique.py. Lets us render an honest
// fraction-of-max bar instead of guessing.
const CATEGORY_MAX: Record<string, number> = {
  hallucination: 25,
  tailoring: 20,
  voice: 15,
  banned_phrases: 15,
  structure: 10,
  gap_handling: 10,
  opening_closing: 5,
  narrative_coherence: 10,
};

function CategoryBar({ name, score }: { name: string; score: number }) {
  const max = CATEGORY_MAX[name] ?? Math.max(score, 10);
  const pct = max > 0 ? Math.max(0, Math.min(100, (score / max) * 100)) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-[11px]">
        <span className="text-slate-700 capitalize">{name.replace(/_/g, " ")}</span>
        <span className="text-slate-500 tabular-nums">
          {score}/{max}
        </span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
        <div
          className="h-full bg-indigo-500 rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
