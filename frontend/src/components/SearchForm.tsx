/**
 * SearchForm — the home-page input. What/Where required, optional
 * filters tucked behind a "More filters" toggle. Submit fires the
 * supplied onSubmit; the parent handles polling and rendering.
 */

import { CalendarPlus, ChevronDown, ChevronUp, Loader2, Search, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import { Input, Label } from "@/components/ui/Input";
import { toast } from "@/components/ui/Toaster";
import { useCreateQuery, useSavedQueries } from "@/hooks/useQueries";
import { MAX_WHAT_TERMS } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { EmploymentType, SearchJobsRequest } from "@/lib/types";

const EMPLOYMENT_LABELS: Record<EmploymentType, string> = {
  FULLTIME: "Full-time",
  PARTTIME: "Part-time",
  CONTRACTOR: "Contract",
  INTERN: "Internship",
};

const POSTED_OPTIONS: Array<{ value: number | undefined; label: string }> = [
  { value: undefined, label: "Any time" },
  { value: 1, label: "Past 24 hours" },
  { value: 3, label: "Past 3 days" },
  { value: 7, label: "Past week" },
];

export interface SearchFormProps {
  initial?: SearchJobsRequest | null;
  disabled: boolean;
  disabledReason?: string;
  isSearching: boolean;
  onSubmit: (spec: SearchJobsRequest) => void;
}

export function SearchForm({
  initial,
  disabled,
  disabledReason,
  isSearching,
  onSubmit,
}: SearchFormProps) {
  const [whatTerms, setWhatTerms] = useState<string[]>(initial?.what ?? []);
  const [whatDraft, setWhatDraft] = useState("");
  const [where, setWhere] = useState(initial?.where ?? "");
  const [salaryMin, setSalaryMin] = useState<string>(
    initial?.salary_min != null ? String(initial.salary_min) : "",
  );
  const [employmentTypes, setEmploymentTypes] = useState<EmploymentType[]>(
    initial?.employment_types ?? [],
  );
  const [postedWithin, setPostedWithin] = useState<number | undefined>(
    initial?.posted_within_days ?? undefined,
  );
  const [topN, setTopN] = useState<string>(
    initial?.top_n != null ? String(initial.top_n) : "",
  );
  const [showMore, setShowMore] = useState(false);
  const createDaily = useCreateQuery();
  const savedQueriesQuery = useSavedQueries();

  const commitWhat = () => {
    const v = whatDraft.trim();
    if (!v) return;
    if (whatTerms.length >= MAX_WHAT_TERMS) return;
    if (whatTerms.some((t) => t.toLowerCase() === v.toLowerCase())) {
      setWhatDraft("");
      return;
    }
    setWhatTerms([...whatTerms, v]);
    setWhatDraft("");
  };

  // Treat the still-uncommitted draft as a term so users don't have to
  // press Enter before clicking Find jobs.
  const effectiveTerms = whatDraft.trim()
    ? [...whatTerms, whatDraft.trim()].slice(0, MAX_WHAT_TERMS)
    : whatTerms;

  const ready =
    !disabled &&
    !isSearching &&
    effectiveTerms.length > 0 &&
    where.trim().length > 0;
  const canSaveDaily =
    effectiveTerms.length > 0 &&
    !!where.trim() &&
    !isSearching &&
    !createDaily.isPending;

  const saveAsDaily = () => {
    // Daily auto-search rows are still single-term (SavedQuery model
    // hasn't grown multi-term yet). Save one row per term, skipping any
    // that already exist with the same what/where.
    const existing = savedQueriesQuery.data?.queries ?? [];
    const trimmedWhere = where.trim().toLowerCase();
    const isDup = (term: string) =>
      existing.some(
        (q) =>
          q.what.trim().toLowerCase() === term.toLowerCase() &&
          q.where.trim().toLowerCase() === trimmedWhere,
      );

    const toAdd = effectiveTerms.filter((t) => !isDup(t));
    const skipped = effectiveTerms.length - toAdd.length;

    if (toAdd.length === 0) {
      toast(`Already in your daily searches${skipped > 1 ? "" : ""}.`);
      return;
    }

    Promise.all(
      toAdd.map(
        (term) =>
          new Promise<void>((resolve, reject) => {
            createDaily.mutate(
              { what: term, where: where.trim() },
              { onSuccess: () => resolve(), onError: (e) => reject(e) },
            );
          }),
      ),
    )
      .then(() => {
        const summary =
          skipped > 0
            ? `Added ${toAdd.length}, skipped ${skipped} duplicate${skipped === 1 ? "" : "s"}.`
            : `Added ${toAdd.length} daily search${toAdd.length === 1 ? "" : "es"}. Manage in Settings.`;
        toast.success(summary);
      })
      .catch((err: Error) =>
        toast.error(`Couldn't save: ${err.message}`),
      );
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready) return;
    const salary = salaryMin.trim() ? Number(salaryMin) : undefined;
    const top = topN.trim() ? Number(topN) : undefined;
    onSubmit({
      what: effectiveTerms,
      where: where.trim(),
      salary_min: Number.isFinite(salary) ? salary : undefined,
      employment_types: employmentTypes.length ? employmentTypes : undefined,
      posted_within_days: postedWithin,
      top_n: Number.isFinite(top) ? top : undefined,
    });
    setWhatDraft("");
  };

  const toggleEmployment = (v: EmploymentType) => {
    setEmploymentTypes((prev) =>
      prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v],
    );
  };

  return (
    <Card>
      <CardContent className="py-5">
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-[2fr_2fr_auto] gap-3 sm:items-end">
            <div>
              <Label htmlFor="what">
                What{" "}
                <span className="text-[10px] text-slate-400 font-normal">
                  · up to {MAX_WHAT_TERMS} role terms
                </span>
              </Label>
              <div
                className={cn(
                  "mt-1 flex flex-wrap items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1.5",
                  "focus-within:ring-2 focus-within:ring-indigo-500/20 focus-within:border-indigo-500",
                  (disabled || isSearching) && "bg-slate-50",
                )}
              >
                {whatTerms.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-900"
                  >
                    {tag}
                    <button
                      type="button"
                      disabled={disabled || isSearching}
                      onClick={() =>
                        setWhatTerms(whatTerms.filter((t) => t !== tag))
                      }
                      className="hover:text-indigo-700"
                      aria-label={`Remove ${tag}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                <input
                  id="what"
                  type="text"
                  placeholder={
                    whatTerms.length === 0
                      ? "e.g. data scientist"
                      : whatTerms.length < MAX_WHAT_TERMS
                        ? "add another…"
                        : ""
                  }
                  value={whatDraft}
                  onChange={(e) => setWhatDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === ",") {
                      e.preventDefault();
                      commitWhat();
                    } else if (
                      e.key === "Backspace" &&
                      !whatDraft &&
                      whatTerms.length > 0
                    ) {
                      setWhatTerms(whatTerms.slice(0, -1));
                    }
                  }}
                  onBlur={commitWhat}
                  disabled={
                    disabled ||
                    isSearching ||
                    whatTerms.length >= MAX_WHAT_TERMS
                  }
                  autoFocus
                  className={cn(
                    "flex-1 min-w-[8rem] bg-transparent outline-none text-sm text-slate-900",
                    "placeholder:text-slate-400 disabled:cursor-not-allowed",
                  )}
                />
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                Press Enter to add a term. Each runs its own search and
                results merge.
              </p>
            </div>
            <div>
              <Label htmlFor="where">Where</Label>
              <Input
                id="where"
                placeholder="e.g. Halifax, Canada"
                value={where}
                onChange={(e) => setWhere(e.target.value)}
                disabled={disabled || isSearching}
                className="mt-1"
              />
            </div>
            <Button
              type="submit"
              disabled={!ready}
              title={disabled ? disabledReason : undefined}
              className="sm:mb-0"
            >
              {isSearching ? <Loader2 className="animate-spin" /> : <Search />}
              {isSearching
                ? "Searching…"
                : disabled
                  ? "Search"
                  : "Find jobs"}
            </Button>
          </div>

          <div className="flex items-center justify-between gap-3 flex-wrap">
            <button
              type="button"
              onClick={() => setShowMore((v) => !v)}
              className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900"
            >
              {showMore ? (
                <ChevronUp className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
              More filters
            </button>
            <button
              type="button"
              onClick={saveAsDaily}
              disabled={!canSaveDaily}
              title="Add this what/where to Daily auto-search in Settings"
              className={cn(
                "inline-flex items-center gap-1 text-xs",
                canSaveDaily
                  ? "text-indigo-700 hover:text-indigo-900"
                  : "text-slate-400 cursor-not-allowed",
              )}
            >
              <CalendarPlus className="h-3 w-3" />
              {createDaily.isPending ? "Saving…" : "Save as daily search"}
            </button>
          </div>

          {showMore && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2 border-t border-slate-100">
              <div>
                <Label htmlFor="salary_min">Min salary (USD)</Label>
                <Input
                  id="salary_min"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  step={5000}
                  placeholder="120000"
                  value={salaryMin}
                  onChange={(e) => setSalaryMin(e.target.value)}
                  disabled={disabled || isSearching}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="top_n">Max results</Label>
                <Input
                  id="top_n"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={200}
                  step={5}
                  placeholder="50"
                  value={topN}
                  onChange={(e) => setTopN(e.target.value)}
                  disabled={disabled || isSearching}
                  className="mt-1"
                />
                <p className="text-[10px] text-slate-500 mt-1">
                  Default 50. Higher = more browsing freedom; lower = only
                  the best matches.
                </p>
              </div>
              <div>
                <Label>Employment type</Label>
                <div className="mt-2 grid grid-cols-2 gap-1.5">
                  {(Object.keys(EMPLOYMENT_LABELS) as EmploymentType[]).map(
                    (v) => (
                      <label
                        key={v}
                        className="inline-flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer"
                      >
                        <Checkbox
                          checked={employmentTypes.includes(v)}
                          onCheckedChange={() => toggleEmployment(v)}
                          disabled={disabled || isSearching}
                        />
                        {EMPLOYMENT_LABELS[v]}
                      </label>
                    ),
                  )}
                </div>
              </div>
              <div>
                <Label>Posted</Label>
                <div className="mt-2 flex flex-col gap-1">
                  {POSTED_OPTIONS.map((opt) => (
                    <label
                      key={opt.label}
                      className={cn(
                        "inline-flex items-center gap-1.5 text-xs cursor-pointer",
                        postedWithin === opt.value
                          ? "text-slate-900"
                          : "text-slate-700",
                      )}
                    >
                      <input
                        type="radio"
                        name="posted_within"
                        checked={postedWithin === opt.value}
                        onChange={() => setPostedWithin(opt.value)}
                        disabled={disabled || isSearching}
                        className="accent-indigo-600"
                      />
                      {opt.label}
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {disabled && disabledReason && (
            <p className="text-xs text-slate-500">{disabledReason}</p>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
