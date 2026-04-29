/**
 * FitBadge — color-coded pill for the agent's fit assessment.
 *
 * Color mapping locked in design_system.md:
 *   HIGH    → emerald
 *   MEDIUM  → amber
 *   LOW     → rose
 *   null    → "Not assessed" in slate
 */

import type { FitAssessment } from "@/lib/types";
import { cn } from "@/lib/utils";

interface FitBadgeProps {
  fit: FitAssessment | null;
  className?: string;
}

const STYLES: Record<FitAssessment, string> = {
  HIGH: "bg-emerald-50 text-emerald-700 border-emerald-200",
  MEDIUM: "bg-amber-50 text-amber-700 border-amber-200",
  LOW: "bg-rose-50 text-rose-700 border-rose-200",
};

const LABELS: Record<FitAssessment, string> = {
  HIGH: "HIGH fit",
  MEDIUM: "MEDIUM fit",
  LOW: "LOW fit",
};

export function FitBadge({ fit, className }: FitBadgeProps) {
  const style = fit
    ? STYLES[fit]
    : "bg-slate-100 text-slate-500 border-slate-200";
  const label = fit ? LABELS[fit] : "Not assessed";
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
        style,
        className,
      )}
      title={
        fit
          ? `Agent assessed this job as a ${fit.toLowerCase()} fit during letter generation`
          : "No letter generated yet — fit will be assessed when you generate"
      }
    >
      {label}
    </span>
  );
}
