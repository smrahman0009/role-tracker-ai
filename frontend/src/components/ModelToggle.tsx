/**
 * ModelToggle — small two-button group for picking Sonnet vs Haiku
 * on a per-panel basis. Used by the JD summary and the cover-letter
 * draft panels so the user can A/B test cost vs quality.
 *
 * Sonnet is the default (better prose) and is shown on the left.
 * Haiku is the cheaper option on the right.
 */

import type { ModelChoice } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  value: ModelChoice;
  onChange: (next: ModelChoice) => void;
  disabled?: boolean;
}

const COMMON =
  "px-2.5 py-1 text-[11px] font-medium border transition-colors " +
  "focus:outline-none focus:ring-2 focus:ring-indigo-400/40 focus:z-10";

export function ModelToggle({ value, onChange, disabled }: Props) {
  return (
    <div
      role="group"
      aria-label="Choose model"
      className="inline-flex rounded-md overflow-hidden shadow-sm"
    >
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange("sonnet")}
        title="Sonnet — better prose, ~5x more expensive"
        className={cn(
          COMMON,
          "rounded-l-md",
          value === "sonnet"
            ? "bg-indigo-600 text-white border-indigo-600"
            : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50",
          disabled && "opacity-50 cursor-not-allowed",
        )}
      >
        Sonnet
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange("haiku")}
        title="Haiku — cheaper, faster, less nuanced prose"
        className={cn(
          COMMON,
          "rounded-r-md -ml-px",
          value === "haiku"
            ? "bg-indigo-600 text-white border-indigo-600"
            : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50",
          disabled && "opacity-50 cursor-not-allowed",
        )}
      >
        Haiku
      </button>
    </div>
  );
}
