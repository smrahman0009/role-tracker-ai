/**
 * UsagePage — three provider cards (JSearch quota / OpenAI / Anthropic)
 * showing the current month's external-API spend, plus a small history
 * table of prior months.
 *
 * Costs are labelled "Estimated" — they're computed from per-feature
 * averages in src/role_tracker/usage/store.py, not the actual
 * Anthropic / OpenAI dashboards. Treat as a budget signal, not a bill.
 */

import {
  ArrowLeft,
  Bot,
  Search as SearchIcon,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router";

import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { useUsage } from "@/hooks/useUsage";
import type { FeatureCount, UsageMonth } from "@/lib/types";
import { cn } from "@/lib/utils";

// JSearch's RapidAPI free tier is 200 requests/month at time of writing.
// Surface as an at-a-glance progress bar; the precise plan limit can
// move to user profile later if anyone upgrades.
const JSEARCH_MONTHLY_QUOTA = 200;

const FEATURE_LABELS: Record<string, string> = {
  embedding: "Embeddings (matching)",
  cover_letter_generate: "Cover letter — generate",
  cover_letter_refine: "Cover letter — refine",
  cover_letter_polish: "Cover letter — polish",
  why_interested_generate: "Why interested — generate",
  why_interested_polish: "Why interested — polish",
  url_extract_llm_refine: "URL extract — refine",
};

function formatUsd(n: number): string {
  if (n === 0) return "$0.00";
  if (n < 0.01) return "<$0.01";
  return `$${n.toFixed(2)}`;
}

function formatYearMonth(ym: string): string {
  const [year, month] = ym.split("-").map(Number);
  if (!year || !month) return ym;
  const date = new Date(Date.UTC(year, month - 1, 1));
  return date.toLocaleString("en-US", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export default function UsagePage() {
  const query = useUsage();

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <Button asChild variant="ghost" size="sm" className="mb-4">
        <Link to="/">
          <ArrowLeft />
          Back to search
        </Link>
      </Button>

      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
          Usage & quota
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          External-API calls this month, with rough cost estimates. Real
          billing lives on the Anthropic and OpenAI dashboards — these
          numbers are a budget signal, not a bill.
        </p>
      </div>

      {query.isLoading ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-slate-500">
            Loading…
          </CardContent>
        </Card>
      ) : query.isError ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-sm font-semibold text-slate-900">
              Couldn't load usage
            </p>
            <p className="text-xs text-slate-600 mt-1">
              {query.error.message}
            </p>
            <Button onClick={() => query.refetch()} className="mt-4">
              Try again
            </Button>
          </CardContent>
        </Card>
      ) : query.data ? (
        <div className="flex flex-col gap-4">
          <p className="text-xs text-slate-500 tabular-nums">
            Current month: {formatYearMonth(query.data.current.year_month)}
          </p>
          <JSearchCard month={query.data.current} />
          <OpenAICard month={query.data.current} />
          <AnthropicCard month={query.data.current} />

          {query.data.history.length > 0 && (
            <HistoryTable history={query.data.history} />
          )}
        </div>
      ) : null}
    </div>
  );
}


function JSearchCard({ month }: { month: UsageMonth }) {
  const used = month.jsearch_calls;
  const cap = JSEARCH_MONTHLY_QUOTA;
  const pct = Math.min(100, (used / cap) * 100);
  const tone =
    pct >= 90
      ? "bg-rose-500"
      : pct >= 70
        ? "bg-amber-500"
        : "bg-indigo-500";

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <SearchIcon className="h-4 w-4 text-slate-500" />
        <h2 className="text-sm font-semibold text-slate-900">JSearch</h2>
      </div>
      <p className="text-xs text-slate-500 mt-0.5">
        Job-fetch requests this month. Each refresh / search burns one
        per saved query.
      </p>

      <div className="mt-4 flex items-baseline justify-between">
        <span className="text-2xl font-semibold tabular-nums text-slate-900">
          {used}
          <span className="text-sm font-normal text-slate-500"> / {cap}</span>
        </span>
        <span className="text-xs text-slate-500 tabular-nums">
          {pct.toFixed(0)}% used
        </span>
      </div>

      <div className="mt-2 h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
        <div
          className={cn("h-full transition-all", tone)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </Card>
  );
}


function OpenAICard({ month }: { month: UsageMonth }) {
  const embedding = month.feature_calls.find(
    (f) => f.feature === "embedding",
  );
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-emerald-600" />
        <h2 className="text-sm font-semibold text-slate-900">OpenAI</h2>
        <span className="ml-auto text-[10px] uppercase tracking-wide text-slate-400">
          Estimated
        </span>
      </div>
      <p className="text-xs text-slate-500 mt-0.5">
        Resume + job embeddings used to score matches.
      </p>

      <div className="mt-4 flex items-baseline justify-between">
        <span className="text-2xl font-semibold tabular-nums text-slate-900">
          {formatUsd(month.estimated_openai_cost_usd)}
        </span>
        <span className="text-xs text-slate-500 tabular-nums">
          {embedding?.count ?? 0} embedding{embedding?.count === 1 ? "" : "s"}
        </span>
      </div>
    </Card>
  );
}


function AnthropicCard({ month }: { month: UsageMonth }) {
  const features = month.feature_calls.filter(
    (f) => f.feature !== "embedding",
  );
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <Bot className="h-4 w-4 text-indigo-600" />
        <h2 className="text-sm font-semibold text-slate-900">Anthropic</h2>
        <span className="ml-auto text-[10px] uppercase tracking-wide text-slate-400">
          Estimated
        </span>
      </div>
      <p className="text-xs text-slate-500 mt-0.5">
        Cover-letter agent loop, refinements, polish passes, and
        URL-extract refinements.
      </p>

      <div className="mt-4 flex items-baseline justify-between">
        <span className="text-2xl font-semibold tabular-nums text-slate-900">
          {formatUsd(month.estimated_anthropic_cost_usd)}
        </span>
        <span className="text-xs text-slate-500 tabular-nums">
          {features.reduce((acc, f) => acc + f.count, 0)} calls
        </span>
      </div>

      {features.length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-100 flex flex-col gap-1.5">
          {features.map((f) => (
            <FeatureRow key={f.feature} fc={f} />
          ))}
        </div>
      )}
    </Card>
  );
}


function FeatureRow({ fc }: { fc: FeatureCount }) {
  return (
    <div className="grid grid-cols-[1fr_auto_auto] items-baseline gap-3 text-xs">
      <span className="text-slate-700 truncate">
        {FEATURE_LABELS[fc.feature] ?? fc.feature}
      </span>
      <span className="text-slate-500 tabular-nums">
        {fc.count} call{fc.count === 1 ? "" : "s"}
      </span>
      <span className="text-slate-900 tabular-nums w-14 text-right">
        {formatUsd(fc.estimated_cost_usd)}
      </span>
    </div>
  );
}


function HistoryTable({ history }: { history: UsageMonth[] }) {
  return (
    <Card className="p-5">
      <h2 className="text-sm font-semibold text-slate-900">Prior months</h2>
      <p className="text-xs text-slate-500 mt-0.5">
        Up to six months are kept. Older rollups are pruned.
      </p>
      <div className="mt-3 grid grid-cols-[1fr_auto_auto_auto] gap-x-4 gap-y-1.5 text-xs">
        <span className="text-[10px] uppercase tracking-wide text-slate-500">
          Month
        </span>
        <span className="text-[10px] uppercase tracking-wide text-slate-500 text-right">
          JSearch
        </span>
        <span className="text-[10px] uppercase tracking-wide text-slate-500 text-right">
          OpenAI
        </span>
        <span className="text-[10px] uppercase tracking-wide text-slate-500 text-right">
          Anthropic
        </span>
        {history.map((m) => (
          <RowFragment key={m.year_month} m={m} />
        ))}
      </div>
    </Card>
  );
}


function RowFragment({ m }: { m: UsageMonth }) {
  return (
    <>
      <span className="text-slate-800">{formatYearMonth(m.year_month)}</span>
      <span className="text-slate-700 tabular-nums text-right">
        {m.jsearch_calls}
      </span>
      <span className="text-slate-700 tabular-nums text-right">
        {formatUsd(m.estimated_openai_cost_usd)}
      </span>
      <span className="text-slate-700 tabular-nums text-right">
        {formatUsd(m.estimated_anthropic_cost_usd)}
      </span>
    </>
  );
}
