/**
 * SearchForm — the home-page input. What/Where required, optional
 * filters tucked behind a "More filters" toggle. Submit fires the
 * supplied onSubmit; the parent handles polling and rendering.
 */

import { ChevronDown, ChevronUp, Loader2, Search } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import { Input, Label } from "@/components/ui/Input";
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
  const [what, setWhat] = useState(initial?.what ?? "");
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
  const [showMore, setShowMore] = useState(false);

  const ready = !disabled && !isSearching && what.trim() && where.trim();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready) return;
    const salary = salaryMin.trim() ? Number(salaryMin) : undefined;
    onSubmit({
      what: what.trim(),
      where: where.trim(),
      salary_min: Number.isFinite(salary) ? salary : undefined,
      employment_types: employmentTypes.length ? employmentTypes : undefined,
      posted_within_days: postedWithin,
    });
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
              <Label htmlFor="what">What</Label>
              <Input
                id="what"
                placeholder="e.g. data scientist"
                value={what}
                onChange={(e) => setWhat(e.target.value)}
                disabled={disabled || isSearching}
                autoFocus
                className="mt-1"
              />
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

          {showMore && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 border-t border-slate-100">
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
