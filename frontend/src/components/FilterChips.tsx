/**
 * FilterChips — chip row above the Job List with multi-select popovers
 * for type/location/employment, a salary input, and a posted-within
 * radio. State is owned by the parent (it lives in URL params); this
 * component is purely controlled.
 */

import { Check, ChevronDown, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Checkbox } from "@/components/ui/Checkbox";
import { Input, Label } from "@/components/ui/Input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/Popover";
import { cn } from "@/lib/utils";
import type { EmploymentType, JobListFilters } from "@/lib/types";

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

export interface FilterChipsProps {
  filters: JobListFilters;
  onChange: (next: JobListFilters) => void;
  locationOptions: string[];
}

export function FilterChips({
  filters,
  onChange,
  locationOptions,
}: FilterChipsProps) {
  const activeCount = countActive(filters);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <TagInputChip
        label="Job type"
        placeholder="e.g. data scientist"
        selected={filters.type ?? []}
        onChange={(v) => onChange({ ...filters, type: v.length ? v : undefined })}
      />
      <MultiSelectChip
        label="Location"
        options={locationOptions}
        selected={filters.location ?? []}
        onChange={(v) =>
          onChange({ ...filters, location: v.length ? v : undefined })
        }
      />
      <SalaryChip filters={filters} onChange={onChange} />
      <EmploymentChip filters={filters} onChange={onChange} />
      <PostedChip filters={filters} onChange={onChange} />

      {activeCount > 0 && (
        <button
          type="button"
          onClick={() =>
            onChange({ filter: filters.filter })
          }
          className="text-xs text-slate-500 hover:text-slate-900 underline underline-offset-2 ml-1"
        >
          Clear all
        </button>
      )}
    </div>
  );
}

function ChipButton({
  active,
  children,
}: {
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <PopoverTrigger asChild>
      <button
        type="button"
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5",
          "text-xs font-medium transition-colors",
          "focus:outline-none focus:ring-2 focus:ring-indigo-500/30",
          active
            ? "border-indigo-300 bg-indigo-50 text-indigo-900 hover:bg-indigo-100"
            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
        )}
      >
        {children}
        <ChevronDown className="h-3 w-3 opacity-60" />
      </button>
    </PopoverTrigger>
  );
}

function TagInputChip({
  label,
  placeholder,
  selected,
  onChange,
}: {
  label: string;
  placeholder?: string;
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  const summary =
    selected.length === 0
      ? label
      : selected.length === 1
        ? `${label}: ${selected[0]}`
        : `${label}: ${selected.length}`;

  const commit = () => {
    const v = draft.trim();
    if (!v) return;
    if (!selected.some((s) => s.toLowerCase() === v.toLowerCase())) {
      onChange([...selected, v]);
    }
    setDraft("");
  };

  return (
    <Popover>
      <ChipButton active={selected.length > 0}>{summary}</ChipButton>
      <PopoverContent className="w-64">
        <Label className="text-xs">{label}</Label>
        <Input
          placeholder={placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              commit();
            } else if (e.key === "Backspace" && !draft && selected.length) {
              onChange(selected.slice(0, -1));
            }
          }}
          onBlur={commit}
          className="mt-1 h-8 text-xs"
        />
        {selected.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {selected.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-900"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => onChange(selected.filter((s) => s !== tag))}
                  className="hover:text-indigo-700"
                  aria-label={`Remove ${tag}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
        <p className="mt-2 text-[11px] text-slate-500">
          Press Enter to add. Matches job-title substrings.
        </p>
      </PopoverContent>
    </Popover>
  );
}

function MultiSelectChip({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? options.filter((o) => o.toLowerCase().includes(q)) : options;
  }, [options, query]);

  const summary =
    selected.length === 0
      ? label
      : selected.length === 1
        ? `${label}: ${selected[0]}`
        : `${label}: ${selected.length}`;

  const toggle = (value: string) => {
    onChange(
      selected.includes(value)
        ? selected.filter((s) => s !== value)
        : [...selected, value],
    );
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <ChipButton active={selected.length > 0}>{summary}</ChipButton>
      <PopoverContent className="w-64">
        <Input
          placeholder={`Search ${label.toLowerCase()}…`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="mb-2 h-8 text-xs"
        />
        <div className="max-h-56 overflow-y-auto -mx-1">
          {filtered.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-slate-500">
              No options
            </p>
          ) : (
            filtered.map((opt) => {
              const isOn = selected.includes(opt);
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => toggle(opt)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded px-2 py-1.5",
                    "text-left text-xs text-slate-700 hover:bg-slate-100",
                  )}
                >
                  <span
                    className={cn(
                      "flex h-4 w-4 items-center justify-center rounded border",
                      isOn
                        ? "bg-indigo-600 border-indigo-600 text-white"
                        : "border-slate-300",
                    )}
                  >
                    {isOn && <Check className="h-3 w-3" strokeWidth={3} />}
                  </span>
                  <span className="truncate">{opt}</span>
                </button>
              );
            })
          )}
        </div>
        {selected.length > 0 && (
          <button
            type="button"
            onClick={() => onChange([])}
            className="mt-2 flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900"
          >
            <X className="h-3 w-3" />
            Clear
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}

function SalaryChip({
  filters,
  onChange,
}: {
  filters: JobListFilters;
  onChange: (next: JobListFilters) => void;
}) {
  const active = filters.salary_min != null || Boolean(filters.hide_no_salary);
  const summary =
    filters.salary_min != null
      ? `Salary ≥ $${Math.round(filters.salary_min / 1000)}k`
      : filters.hide_no_salary
        ? "Salary listed"
        : "Salary";

  return (
    <Popover>
      <ChipButton active={active}>{summary}</ChipButton>
      <PopoverContent className="w-64">
        <Label htmlFor="salary-min" className="text-xs">
          Minimum salary (USD)
        </Label>
        <Input
          id="salary-min"
          type="number"
          inputMode="numeric"
          min={0}
          step={5000}
          placeholder="e.g. 120000"
          value={filters.salary_min ?? ""}
          onChange={(e) => {
            const v = e.target.value;
            onChange({
              ...filters,
              salary_min: v === "" ? undefined : Number(v),
            });
          }}
          className="mt-1 h-8 text-xs"
        />
        <label className="mt-3 flex items-center gap-2 text-xs text-slate-700">
          <Checkbox
            checked={Boolean(filters.hide_no_salary)}
            onCheckedChange={(c) =>
              onChange({ ...filters, hide_no_salary: c === true ? true : undefined })
            }
          />
          Hide jobs without a salary
        </label>
        {active && (
          <button
            type="button"
            onClick={() =>
              onChange({ ...filters, salary_min: undefined, hide_no_salary: undefined })
            }
            className="mt-3 flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900"
          >
            <X className="h-3 w-3" />
            Clear
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}

function EmploymentChip({
  filters,
  onChange,
}: {
  filters: JobListFilters;
  onChange: (next: JobListFilters) => void;
}) {
  const selected = filters.employment_types ?? [];
  const active = selected.length > 0;
  const summary =
    selected.length === 0
      ? "Employment"
      : selected.length === 1
        ? EMPLOYMENT_LABELS[selected[0]]
        : `Employment: ${selected.length}`;

  const toggle = (v: EmploymentType) => {
    const next = selected.includes(v)
      ? selected.filter((s) => s !== v)
      : [...selected, v];
    onChange({
      ...filters,
      employment_types: next.length ? next : undefined,
    });
  };

  return (
    <Popover>
      <ChipButton active={active}>{summary}</ChipButton>
      <PopoverContent className="w-52">
        <div className="flex flex-col gap-1">
          {(Object.keys(EMPLOYMENT_LABELS) as EmploymentType[]).map((v) => (
            <label
              key={v}
              className="flex items-center gap-2 rounded px-2 py-1.5 text-xs text-slate-700 hover:bg-slate-100 cursor-pointer"
            >
              <Checkbox
                checked={selected.includes(v)}
                onCheckedChange={() => toggle(v)}
              />
              {EMPLOYMENT_LABELS[v]}
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function PostedChip({
  filters,
  onChange,
}: {
  filters: JobListFilters;
  onChange: (next: JobListFilters) => void;
}) {
  const value = filters.posted_within_days;
  const active = value != null;
  const current = POSTED_OPTIONS.find((o) => o.value === value) ?? POSTED_OPTIONS[0];

  return (
    <Popover>
      <ChipButton active={active}>
        {active ? current.label : "Posted"}
      </ChipButton>
      <PopoverContent className="w-48">
        <div className="flex flex-col gap-1">
          {POSTED_OPTIONS.map((opt) => {
            const isOn = opt.value === value;
            return (
              <button
                key={opt.label}
                type="button"
                onClick={() =>
                  onChange({ ...filters, posted_within_days: opt.value })
                }
                className={cn(
                  "flex items-center justify-between rounded px-2 py-1.5",
                  "text-left text-xs hover:bg-slate-100",
                  isOn ? "text-indigo-900 font-medium" : "text-slate-700",
                )}
              >
                {opt.label}
                {isOn && <Check className="h-3 w-3 text-indigo-600" strokeWidth={3} />}
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function countActive(f: JobListFilters): number {
  let n = 0;
  if (f.type?.length) n++;
  if (f.location?.length) n++;
  if (f.salary_min != null) n++;
  if (f.hide_no_salary) n++;
  if (f.employment_types?.length) n++;
  if (f.posted_within_days != null) n++;
  return n;
}
