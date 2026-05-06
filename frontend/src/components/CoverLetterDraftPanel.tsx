/**
 * CoverLetterDraftPanel — Phase 2 of the interactive cover-letter flow.
 *
 * Below the match analysis, the user sees three paragraph cards:
 * Hook, Fit, Close. The flow:
 *
 *   1. Click "Compose draft" — fires three parallel /draft calls,
 *      one per paragraph.
 *   2. Each card lands in *Viewing* state with the generated text.
 *   3. Click "Tweak this" → *Tweaking* state (textarea + Save / Cancel).
 *   4. Once all three paragraphs are non-empty, "Finalize and save"
 *      enables. Click → POST /finalize → letter saved with
 *      edited_by_user=true. The existing letter workspace refetches.
 *
 * No alternatives or hints yet (those land in Phases 3-4). No Sonnet
 * smoothing pass at finalize time yet (Phase 6).
 */

import { useEffect, useMemo, useState } from "react";
import { Loader2, Sparkles, Check } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { toast } from "@/components/ui/Toaster";
import { useCoverLetterAnalysis } from "@/hooks/useCoverLetterAnalysis";
import {
  useCoverLetterDraft,
  useCoverLetterFinalize,
} from "@/hooks/useCoverLetterDraft";
import type {
  CoverLetterAnalysisResponse,
  CoverLetterCommitted,
  ParagraphKey,
} from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  jobId: string;
}

type CardState = "empty" | "loading" | "viewing" | "tweaking";

interface ParagraphState {
  text: string;
  draftEdit: string;
  status: CardState;
  error?: string;
}

const EMPTY_PARAGRAPH: ParagraphState = {
  text: "",
  draftEdit: "",
  status: "empty",
};

const PARAGRAPH_LABELS: Record<ParagraphKey, string> = {
  hook: "Paragraph 1, Hook",
  fit: "Paragraph 2, Why you're a fit",
  close: "Paragraph 3, Close",
};

export function CoverLetterDraftPanel({ jobId }: Props) {
  const analysisQuery = useCoverLetterAnalysis(jobId);
  const analysis = analysisQuery.data;
  const draftMutation = useCoverLetterDraft(jobId);
  const finalizeMutation = useCoverLetterFinalize(jobId);

  const [paragraphs, setParagraphs] = useState<
    Record<ParagraphKey, ParagraphState>
  >({
    hook: { ...EMPTY_PARAGRAPH },
    fit: { ...EMPTY_PARAGRAPH },
    close: { ...EMPTY_PARAGRAPH },
  });

  // Reset whenever the user opens a different job (analysis changes).
  useEffect(() => {
    setParagraphs({
      hook: { ...EMPTY_PARAGRAPH },
      fit: { ...EMPTY_PARAGRAPH },
      close: { ...EMPTY_PARAGRAPH },
    });
  }, [jobId]);

  const allReady = useMemo(
    () =>
      paragraphs.hook.text.trim().length > 0 &&
      paragraphs.fit.text.trim().length > 0 &&
      paragraphs.close.text.trim().length > 0,
    [paragraphs],
  );

  if (!analysis) {
    return null;
  }

  const composeAll = async () => {
    const keys: ParagraphKey[] = ["hook", "fit", "close"];

    // Mark all three as loading immediately so the user sees activity.
    setParagraphs((prev) => {
      const next = { ...prev };
      for (const k of keys) {
        next[k] = { ...prev[k], status: "loading", error: undefined };
      }
      return next;
    });

    const committed: CoverLetterCommitted = {
      hook: null,
      fit: null,
      close: null,
    };

    await Promise.all(
      keys.map(async (paragraph) => {
        try {
          const result = await draftMutation.mutateAsync({
            paragraph,
            analysis,
            committed,
          });
          setParagraphs((prev) => ({
            ...prev,
            [paragraph]: {
              text: result.text,
              draftEdit: result.text,
              status: "viewing",
            },
          }));
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Generation failed";
          setParagraphs((prev) => ({
            ...prev,
            [paragraph]: { ...prev[paragraph], status: "empty", error: msg },
          }));
          toast.error(`${paragraph} failed: ${msg}`);
        }
      }),
    );
  };

  const startTweak = (key: ParagraphKey) => {
    setParagraphs((prev) => ({
      ...prev,
      [key]: { ...prev[key], status: "tweaking", draftEdit: prev[key].text },
    }));
  };

  const cancelTweak = (key: ParagraphKey) => {
    setParagraphs((prev) => ({
      ...prev,
      [key]: { ...prev[key], status: "viewing", draftEdit: prev[key].text },
    }));
  };

  const saveTweak = (key: ParagraphKey) => {
    setParagraphs((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        status: "viewing",
        text: prev[key].draftEdit.trim(),
      },
    }));
  };

  const onEditChange = (key: ParagraphKey, value: string) => {
    setParagraphs((prev) => ({
      ...prev,
      [key]: { ...prev[key], draftEdit: value },
    }));
  };

  const finalize = () => {
    finalizeMutation.mutate(
      {
        hook: paragraphs.hook.text,
        fit: paragraphs.fit.text,
        close: paragraphs.close.text,
      },
      {
        onSuccess: (letter) => {
          toast.success(`Saved as v${letter.version}`);
        },
        onError: (err) =>
          toast.error(
            err instanceof Error ? err.message : "Couldn't save letter",
          ),
      },
    );
  };

  const noneStarted = (["hook", "fit", "close"] as ParagraphKey[]).every(
    (k) => paragraphs[k].status === "empty",
  );

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Compose cover letter
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Three short paragraphs based on the match analysis above. Edit
            any of them before saving.
          </p>
        </div>
        <Button
          size="sm"
          variant={noneStarted ? "default" : "secondary"}
          onClick={composeAll}
          disabled={
            draftMutation.isPending ||
            (!noneStarted &&
              (["hook", "fit", "close"] as ParagraphKey[]).some(
                (k) => paragraphs[k].status === "loading",
              ))
          }
        >
          {(["hook", "fit", "close"] as ParagraphKey[]).some(
            (k) => paragraphs[k].status === "loading",
          ) ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Drafting
            </>
          ) : noneStarted ? (
            <>
              <Sparkles className="h-3.5 w-3.5" />
              Compose draft
            </>
          ) : (
            "Re-draft all"
          )}
        </Button>
      </div>

      <div className="mt-4 space-y-3">
        {(["hook", "fit", "close"] as ParagraphKey[]).map((key) => (
          <ParagraphCard
            key={key}
            label={PARAGRAPH_LABELS[key]}
            state={paragraphs[key]}
            onTweak={() => startTweak(key)}
            onCancel={() => cancelTweak(key)}
            onSave={() => saveTweak(key)}
            onEditChange={(v) => onEditChange(key, v)}
          />
        ))}
      </div>

      {allReady && (
        <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between gap-3">
          <p className="text-xs text-slate-600">
            All three paragraphs ready. Saving creates a new letter
            version you can download or refine later.
          </p>
          <Button
            onClick={finalize}
            disabled={finalizeMutation.isPending}
            size="sm"
          >
            {finalizeMutation.isPending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Saving
              </>
            ) : (
              <>
                <Check className="h-3.5 w-3.5" />
                Finalize and save
              </>
            )}
          </Button>
        </div>
      )}
    </Card>
  );
}

// ---------- one paragraph card ----------

function ParagraphCard({
  label,
  state,
  onTweak,
  onCancel,
  onSave,
  onEditChange,
}: {
  label: string;
  state: ParagraphState;
  onTweak: () => void;
  onCancel: () => void;
  onSave: () => void;
  onEditChange: (value: string) => void;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-slate-50/50 px-4 py-3",
        state.status === "tweaking" && "border-indigo-300 bg-indigo-50/30",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] uppercase tracking-wide font-medium text-slate-500">
          {label}
        </p>
        {state.status === "viewing" && (
          <Button size="sm" variant="ghost" onClick={onTweak}>
            Tweak
          </Button>
        )}
      </div>

      {state.status === "empty" && (
        <p className="mt-1.5 text-xs text-slate-400 italic">
          {state.error
            ? `Last attempt failed: ${state.error}`
            : "Click Compose draft above to generate."}
        </p>
      )}

      {state.status === "loading" && (
        <p className="mt-1.5 text-xs text-slate-500 inline-flex items-center gap-1.5">
          <Loader2 className="h-3 w-3 animate-spin" />
          Drafting…
        </p>
      )}

      {state.status === "viewing" && (
        <p className="mt-2 text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">
          {state.text}
        </p>
      )}

      {state.status === "tweaking" && (
        <div className="mt-2">
          <textarea
            value={state.draftEdit}
            onChange={(e) => onEditChange(e.target.value)}
            className="w-full min-h-32 text-sm text-slate-800 leading-relaxed bg-white border border-indigo-200 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400/40"
            autoFocus
          />
          <div className="mt-2 flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
            <Button size="sm" onClick={onSave}>
              Save edits
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
