/**
 * JobDetailPage — single-job view. JD on top, cover-letter workspace
 * below: version selector + letter text on the left, strategy and
 * critique panels on the right.
 *
 * State machine for the workspace:
 *   - no versions, no active gen → "Generate cover letter" empty state
 *   - active gen (pending/running) → polling banner
 *   - versions present → letter viewer with current version selected
 *
 * Edits go through the inline textarea (Edit → Save uses the manual
 * edit endpoint, which records edited_by_user=true). Refines and
 * regenerates kick off a generation that we poll, then refetch
 * versions on completion.
 */

import {
  ArrowLeft,
  Building2,
  ExternalLink,
  Loader2,
  MapPin,
  Pencil,
  RefreshCw,
  Save,
  Sparkles,
  Wand,
  Wand2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import { useAuth } from "@/auth/AuthContext";
import { ApplyKitPanel } from "@/components/ApplyKitPanel";
import { CritiquePanel } from "@/components/CritiquePanel";
import { LetterDownloadButton } from "@/components/LetterDownloadButton";
import { LetterRenderer } from "@/components/LetterRenderer";
import { FitBadge } from "@/components/FitBadge";
import { RefineDialog } from "@/components/RefineDialog";
import { StrategyPanel } from "@/components/StrategyPanel";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Input";
import { toast } from "@/components/ui/Toaster";
import { useApplyJob, useJobDetail, useUnapplyJob } from "@/hooks/useJobs";
import {
  useEditLetter,
  useGenerateLetter,
  useLetterGeneration,
  useLetterVersions,
  usePolishLetter,
  useRefineLetter,
  useRegenerateLetter,
} from "@/hooks/useLetters";
import { ApiClientError } from "@/lib/api";
import { formatMatchScore, formatSalary } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Letter } from "@/lib/types";

const MAX_REFINEMENTS = 10;

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const { userId } = useAuth();

  const jobQuery = useJobDetail(jobId);
  const versionsQuery = useLetterVersions(jobId);

  const versions = versionsQuery.data?.versions ?? [];
  const sortedVersions = useMemo(
    () => [...versions].sort((a, b) => b.version - a.version),
    [versions],
  );
  const latest = sortedVersions[0];

  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  useEffect(() => {
    if (selectedVersion == null && latest) setSelectedVersion(latest.version);
  }, [latest, selectedVersion]);
  const current =
    sortedVersions.find((v) => v.version === selectedVersion) ?? latest ?? null;

  // Refinement count is shared across all versions of a job's letter.
  const refinementsUsed = useMemo(
    () => versions.filter((v) => v.refinement_index > 0).length,
    [versions],
  );
  const refinementsRemaining = Math.max(0, MAX_REFINEMENTS - refinementsUsed);

  // Generation polling.
  const [activeGenId, setActiveGenId] = useState<string | null>(null);
  const generation = useLetterGeneration(jobId, activeGenId);
  const generationStatus = generation.data?.status;
  const isGenerating =
    generationStatus === "pending" || generationStatus === "running";

  useEffect(() => {
    if (!activeGenId) return;
    if (generationStatus === "done") {
      toast.success("Cover letter ready");
      versionsQuery.refetch();
      const newVersion = generation.data?.letter?.version ?? null;
      if (newVersion != null) setSelectedVersion(newVersion);
      setActiveGenId(null);
    } else if (generationStatus === "failed") {
      toast.error(`Generation failed: ${generation.data?.error ?? "unknown"}`);
      setActiveGenId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generationStatus]);

  const generateMutation = useGenerateLetter(jobId);
  const regenerateMutation = useRegenerateLetter(jobId);
  const refineMutation = useRefineLetter(jobId, current?.version);
  const editMutation = useEditLetter(jobId, current?.version);
  const applyMutation = useApplyJob();
  const unapplyMutation = useUnapplyJob();

  const startGenerate = () => {
    generateMutation.mutate(undefined, {
      onSuccess: (d) => setActiveGenId(d.generation_id),
      onError: (err) => toast.error(`Generate failed: ${err.message}`),
    });
  };

  const startRegenerate = () => {
    regenerateMutation.mutate(undefined, {
      onSuccess: (d) => setActiveGenId(d.generation_id),
      onError: (err) => toast.error(`Regenerate failed: ${err.message}`),
    });
  };

  const [refineOpen, setRefineOpen] = useState(false);
  const startRefine = (feedback: string) => {
    refineMutation.mutate(feedback, {
      onSuccess: (d) => {
        setRefineOpen(false);
        setActiveGenId(d.generation_id);
      },
      onError: (err) => {
        if (err instanceof ApiClientError && err.status === 422) {
          toast.error(err.message);
        } else {
          toast.error(`Refine failed: ${err.message}`);
        }
      },
    });
  };

  const job = jobQuery.data;

  const handleToggleApplied = () => {
    if (!job) return;
    if (job.applied) {
      unapplyMutation.mutate(job.job_id, {
        onSuccess: () => {
          toast.success("Unmarked as applied");
          jobQuery.refetch();
        },
        onError: (err) => toast.error(err.message),
      });
    } else {
      // Capture which letter version the user has selected at apply
      // time so the My Applications row can show "applied with v3".
      applyMutation.mutate(
        {
          jobId: job.job_id,
          letterVersionUsed: current?.version ?? null,
        },
        {
          onSuccess: () => {
            toast.success("Marked as applied");
            jobQuery.refetch();
          },
          onError: (err) => toast.error(err.message),
        },
      );
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <Button asChild variant="ghost" size="sm" className="mb-4">
        <Link to="/">
          <ArrowLeft />
          Back to jobs
        </Link>
      </Button>

      {jobQuery.isLoading ? (
        <Card className="p-12 animate-pulse">
          <div className="h-5 w-2/3 bg-slate-200 rounded mb-3" />
          <div className="h-3 w-1/3 bg-slate-100 rounded" />
        </Card>
      ) : jobQuery.isError ? (
        <Card className="p-8 text-center">
          <p className="text-sm font-semibold text-slate-900">
            Couldn't load job
          </p>
          <p className="text-xs text-slate-600 mt-1">
            {jobQuery.error.message}
          </p>
          <Button onClick={() => jobQuery.refetch()} className="mt-4">
            Try again
          </Button>
        </Card>
      ) : job ? (
        <>
          <JobHeader
            job={job}
            onToggleApplied={handleToggleApplied}
            isToggling={applyMutation.isPending || unapplyMutation.isPending}
          />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
            <div className="lg:col-span-2 space-y-4">
              <LetterWorkspace
                userId={userId ?? ""}
                jobId={job.job_id}
                versions={sortedVersions}
                current={current}
                isGenerating={isGenerating}
                generationStatus={generationStatus}
                refinementsRemaining={refinementsRemaining}
                onSelectVersion={setSelectedVersion}
                onGenerate={startGenerate}
                onRegenerate={startRegenerate}
                onOpenRefine={() => setRefineOpen(true)}
                editMutation={editMutation}
                regenerateMutationPending={regenerateMutation.isPending}
                generateMutationPending={generateMutation.isPending}
              />
              <JobDescription description={job.description} />
            </div>

            <div className="space-y-4">
              <ApplyKitPanel
                userId={userId ?? ""}
                jobId={job.job_id}
                jobUrl={job.url}
              />
              {current?.strategy && <StrategyPanel strategy={current.strategy} />}
              {current?.critique && <CritiquePanel critique={current.critique} />}
              {current && (
                <RefinementCounter
                  used={refinementsUsed}
                  remaining={refinementsRemaining}
                />
              )}
            </div>
          </div>
        </>
      ) : null}

      <RefineDialog
        open={refineOpen}
        onOpenChange={setRefineOpen}
        remaining={refinementsRemaining}
        isSubmitting={refineMutation.isPending}
        onSubmit={startRefine}
      />
    </div>
  );
}

// ---------- Job header ----------

function JobHeader({
  job,
  onToggleApplied,
  isToggling,
}: {
  job: NonNullable<ReturnType<typeof useJobDetail>["data"]>;
  onToggleApplied: () => void;
  isToggling: boolean;
}) {
  return (
    <Card>
      <CardContent className="py-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-semibold text-slate-900 tracking-tight">
                {job.title}
              </h1>
              <span className="text-sm font-mono text-slate-500 tabular-nums">
                {formatMatchScore(job.match_score)}
              </span>
              <FitBadge fit={job.fit_assessment} />
              {job.applied && (
                <span className="rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11px] font-medium px-2 py-0.5">
                  Applied
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-600 mt-1.5 flex-wrap">
              <span className="flex items-center gap-1">
                <Building2 className="h-3 w-3" />
                {job.company}
              </span>
              <span className="flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                {job.location}
              </span>
              <span>
                {formatSalary(job.salary_min, job.salary_max, {
                  empty: "Salary not listed",
                })}
              </span>
              <span className="text-slate-400">·</span>
              <span>{job.publisher}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button asChild variant="secondary" size="sm">
              <a href={job.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink />
                View posting
              </a>
            </Button>
            <Button
              variant={job.applied ? "secondary" : "primary"}
              size="sm"
              onClick={onToggleApplied}
              disabled={isToggling}
            >
              {job.applied ? "Mark unapplied" : "Mark applied"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function JobDescription({ description }: { description: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Job description</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
          {description}
        </p>
      </CardContent>
    </Card>
  );
}

// ---------- Letter workspace ----------

interface LetterWorkspaceProps {
  userId: string;
  jobId: string;
  versions: Letter[];
  current: Letter | null;
  isGenerating: boolean;
  generationStatus: string | undefined;
  refinementsRemaining: number;
  onSelectVersion: (v: number) => void;
  onGenerate: () => void;
  onRegenerate: () => void;
  onOpenRefine: () => void;
  editMutation: ReturnType<typeof useEditLetter>;
  regenerateMutationPending: boolean;
  generateMutationPending: boolean;
}

function LetterWorkspace({
  userId,
  jobId,
  versions,
  current,
  isGenerating,
  generationStatus,
  refinementsRemaining,
  onSelectVersion,
  onGenerate,
  onRegenerate,
  onOpenRefine,
  editMutation,
  regenerateMutationPending,
  generateMutationPending,
}: LetterWorkspaceProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const polishMutation = usePolishLetter(jobId, current?.version);

  const polishDraft = () => {
    const v = draft.trim();
    if (!v) return;
    polishMutation.mutate(v, {
      onSuccess: (data) => {
        setDraft(data.text);
        toast.success("Polished — meaning preserved");
      },
      onError: (err) => {
        if (err instanceof ApiClientError && err.status === 422) {
          toast.error(err.message);
        } else {
          toast.error(`Polish failed: ${err.message}`);
        }
      },
    });
  };

  useEffect(() => {
    setEditing(false);
    setDraft(current?.text ?? "");
  }, [current?.version]);

  if (versions.length === 0 && !isGenerating) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Sparkles className="h-6 w-6 text-indigo-500 mx-auto" />
          <p className="text-sm font-semibold text-slate-900 mt-3">
            No cover letter yet
          </p>
          <p className="text-xs text-slate-600 mt-1.5 max-w-md mx-auto">
            The agent will read this JD and your resume, commit to a strategy,
            draft a 300-400 word letter, and self-critique. Takes ~60 seconds.
          </p>
          <Button
            onClick={onGenerate}
            disabled={generateMutationPending}
            className="mt-4"
          >
            <Sparkles />
            Generate cover letter
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!current) {
    return <GenerationBanner status={generationStatus} />;
  }

  const saveEdit = () => {
    const v = draft.trim();
    if (!v || v === current.text) {
      setEditing(false);
      return;
    }
    editMutation.mutate(v, {
      onSuccess: (saved) => {
        toast.success(`Edit saved as v${saved.version}`);
        setEditing(false);
        // The edit endpoint creates a *new* version. Jump to it so the
        // workspace shows the user's saved text instead of staying on
        // the version they were editing (which still has the old text).
        onSelectVersion(saved.version);
      },
      onError: (err) => {
        if (err instanceof ApiClientError && err.status === 422) {
          toast.error(err.message);
        } else {
          toast.error(`Save failed: ${err.message}`);
        }
      },
    });
  };

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <CardTitle className="text-sm">Cover letter</CardTitle>
          <VersionSelector
            versions={versions}
            current={current}
            onSelect={onSelectVersion}
          />
          <span className="text-xs text-slate-500">
            {current.word_count} words
          </span>
          {current.edited_by_user && (
            <span className="rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-[10px] font-medium px-1.5 py-0.5">
              Edited
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <LetterDownloadButton
            userId={userId}
            jobId={jobId}
            version={current.version}
            iconOnly
          />
          {editing ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setEditing(false);
                  setDraft(current.text);
                }}
                disabled={editMutation.isPending || polishMutation.isPending}
              >
                <X />
                Cancel
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={polishDraft}
                disabled={
                  editMutation.isPending ||
                  polishMutation.isPending ||
                  !draft.trim()
                }
                title="Fix grammar and clarity in your edits without changing meaning"
              >
                {polishMutation.isPending ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <Wand />
                )}
                {polishMutation.isPending ? "Polishing…" : "Polish"}
              </Button>
              <Button
                size="sm"
                onClick={saveEdit}
                disabled={editMutation.isPending || polishMutation.isPending}
              >
                <Save />
                {editMutation.isPending ? "Saving…" : "Save edit"}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditing(true)}
                disabled={isGenerating}
              >
                <Pencil />
                Edit
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={onOpenRefine}
                disabled={isGenerating || refinementsRemaining <= 0}
                title={
                  refinementsRemaining <= 0
                    ? "10-refinement cap reached for this letter"
                    : undefined
                }
              >
                <Wand2 />
                Refine
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={onRegenerate}
                disabled={isGenerating || regenerateMutationPending}
              >
                <RefreshCw className={isGenerating ? "animate-spin" : ""} />
                Regenerate
              </Button>
            </>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isGenerating && <GenerationBanner status={generationStatus} inline />}
        {editing ? (
          <Textarea
            rows={20}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={editMutation.isPending}
            className="font-mono text-[13px] leading-relaxed"
          />
        ) : (
          <LetterRenderer
            text={current.text}
            className={cn(isGenerating && "opacity-50")}
          />
        )}
      </CardContent>
    </Card>
  );
}

function VersionSelector({
  versions,
  current,
  onSelect,
}: {
  versions: Letter[];
  current: Letter;
  onSelect: (v: number) => void;
}) {
  if (versions.length <= 1) {
    return (
      <span className="text-xs font-medium text-slate-700">
        v{current.version}
      </span>
    );
  }
  return (
    <select
      value={current.version}
      onChange={(e) => onSelect(Number(e.target.value))}
      className="text-xs font-medium rounded border border-slate-200 bg-white px-2 py-1 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
    >
      {versions.map((v) => (
        <option key={v.version} value={v.version}>
          v{v.version}
          {v.refinement_index > 0 ? ` · refine #${v.refinement_index}` : ""}
          {v.edited_by_user ? " · edited" : ""}
        </option>
      ))}
    </select>
  );
}

function GenerationBanner({
  status,
  inline = false,
}: {
  status: string | undefined;
  inline?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-xs text-indigo-900",
        !inline && "mt-1",
        inline && "mb-3",
      )}
    >
      <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
      <span className="font-medium">
        {status === "running"
          ? "Drafting and self-critiquing the letter…"
          : "Starting generation…"}
      </span>
      <span className="text-indigo-700">
        ~60-90 seconds
      </span>
    </div>
  );
}

function RefinementCounter({
  used,
  remaining,
}: {
  used: number;
  remaining: number;
}) {
  const pct = Math.round((used / MAX_REFINEMENTS) * 100);
  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex items-baseline justify-between">
          <p className="text-xs font-medium text-slate-700">Refinements used</p>
          <p className="text-xs text-slate-500 tabular-nums">
            {used} / {MAX_REFINEMENTS}
          </p>
        </div>
        <div className="mt-2 h-1.5 rounded-full bg-slate-100 overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full",
              remaining <= 2 ? "bg-rose-500" : "bg-indigo-500",
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
        {remaining <= 0 && (
          <p className="text-[11px] text-rose-700 mt-2">
            Cap reached. Use Edit for further tweaks, or Regenerate to start fresh.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

