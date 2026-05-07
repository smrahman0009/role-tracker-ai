/**
 * CoverLetterDraftPanel — Phases 2, 2.5, 3 of the interactive flow.
 *
 * Three paragraph cards (Hook, Fit, Close), each with three things
 * the user can do:
 *
 *   - "Tweak"          → inline edit (Phase 2)
 *   - "Try a different angle" → side-by-side alternative (Phase 3)
 *   - "Re-draft all"   → fresh top-level regeneration (Phase 2)
 *
 * Alternatives are capped at MAX_ALTERNATIVES per card. Each
 * alternative is displayed beside the current text with "Use this"
 * (commits it as the new current) and "Discard" (drops just that
 * one) buttons. A "Discard all" link clears every alternative for
 * a card at once.
 *
 * Per-call model toggle (Sonnet / Haiku) at the panel level applies
 * to every draft and alternative call.
 *
 * No hint field yet (Phase 4). No Sonnet smoothing pass at finalize
 * (Phase 6).
 */

import { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Loader2,
  Send,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";

import { ModelToggle } from "@/components/ModelToggle";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { toast } from "@/components/ui/Toaster";
import { useCoverLetterAnalysis } from "@/hooks/useCoverLetterAnalysis";
import {
  useCoverLetterDraft,
  useCoverLetterFinalize,
} from "@/hooks/useCoverLetterDraft";
import type {
  CoverLetterCommitted,
  ModelChoice,
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
  /** Alternates produced by "Try different angle" or by hint-driven
   * regeneration; oldest first. Capped at MAX_ALTERNATIVES. */
  alternatives: string[];
  /** True while a /draft call with alternative_to or hint is in flight. */
  loadingAlternative: boolean;
  /** Phase 4: hint input controls. Open shows the textarea + Apply
   * button; the value is the user's typed steering text. */
  hintOpen: boolean;
  hintValue: string;
  error?: string;
}

const EMPTY_PARAGRAPH: ParagraphState = {
  text: "",
  draftEdit: "",
  status: "empty",
  alternatives: [],
  loadingAlternative: false,
  hintOpen: false,
  hintValue: "",
};

const MAX_ALTERNATIVES = 3;

const PARAGRAPH_LABELS: Record<ParagraphKey, string> = {
  hook: "Paragraph 1, Hook",
  fit: "Paragraph 2, Why you're a fit",
  close: "Paragraph 3, Close",
};

const PARAGRAPH_KEYS: ParagraphKey[] = ["hook", "fit", "close"];

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
  const [model, setModel] = useState<ModelChoice>("sonnet");

  // Reset whenever the user opens a different job.
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
    setParagraphs((prev) => {
      const next = { ...prev };
      for (const k of PARAGRAPH_KEYS) {
        next[k] = {
          ...prev[k],
          status: "loading",
          error: undefined,
          alternatives: [],
        };
      }
      return next;
    });

    const committed: CoverLetterCommitted = {
      hook: null,
      fit: null,
      close: null,
    };

    await Promise.all(
      PARAGRAPH_KEYS.map(async (paragraph) => {
        try {
          const result = await draftMutation.mutateAsync({
            paragraph,
            analysis,
            committed,
            model,
          });
          setParagraphs((prev) => ({
            ...prev,
            [paragraph]: {
              ...prev[paragraph],
              text: result.text,
              draftEdit: result.text,
              status: "viewing",
              alternatives: [],
              loadingAlternative: false,
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

  // Phase 3: alternatives -------------------------------------------

  /**
   * Generate a new alternative for the given paragraph. Optionally
   * steered by a hint — the hint is consumed (cleared) once applied.
   */
  const generateAlternative = async (
    key: ParagraphKey,
    options: { hint?: string } = {},
  ) => {
    const current = paragraphs[key];
    if (!current.text.trim() || current.loadingAlternative) return;

    setParagraphs((prev) => ({
      ...prev,
      [key]: { ...prev[key], loadingAlternative: true, error: undefined },
    }));

    try {
      const result = await draftMutation.mutateAsync({
        paragraph: key,
        analysis,
        committed: { hook: null, fit: null, close: null },
        alternative_to: current.text,
        hint: options.hint?.trim() || undefined,
        model,
      });
      setParagraphs((prev) => {
        const list = [...prev[key].alternatives, result.text];
        const capped =
          list.length > MAX_ALTERNATIVES
            ? list.slice(list.length - MAX_ALTERNATIVES)
            : list;
        return {
          ...prev,
          [key]: {
            ...prev[key],
            alternatives: capped,
            loadingAlternative: false,
            // Hint is consumed: close the input and clear its value
            // so the next "Try a different angle" click without
            // opening the hint UI doesn't accidentally re-apply it.
            hintOpen: false,
            hintValue: "",
          },
        };
      });
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Alternative generation failed";
      setParagraphs((prev) => ({
        ...prev,
        [key]: { ...prev[key], loadingAlternative: false, error: msg },
      }));
      toast.error(msg);
    }
  };

  const tryDifferentAngle = (key: ParagraphKey) =>
    generateAlternative(key);

  const toggleHint = (key: ParagraphKey) => {
    setParagraphs((prev) => ({
      ...prev,
      [key]: { ...prev[key], hintOpen: !prev[key].hintOpen },
    }));
  };

  const onHintChange = (key: ParagraphKey, value: string) => {
    setParagraphs((prev) => ({
      ...prev,
      [key]: { ...prev[key], hintValue: value },
    }));
  };

  const applyHint = (key: ParagraphKey) => {
    const hint = paragraphs[key].hintValue;
    if (!hint.trim()) return;
    void generateAlternative(key, { hint });
  };

  const useAlternative = (key: ParagraphKey, index: number) => {
    setParagraphs((prev) => {
      const chosen = prev[key].alternatives[index];
      if (!chosen) return prev;
      return {
        ...prev,
        [key]: {
          ...prev[key],
          text: chosen,
          draftEdit: chosen,
          alternatives: [],
        },
      };
    });
  };

  const discardAlternative = (key: ParagraphKey, index: number) => {
    setParagraphs((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        alternatives: prev[key].alternatives.filter((_, i) => i !== index),
      },
    }));
  };

  const discardAllAlternatives = (key: ParagraphKey) => {
    setParagraphs((prev) => ({
      ...prev,
      [key]: { ...prev[key], alternatives: [] },
    }));
  };

  // Finalize --------------------------------------------------------

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

  const noneStarted = PARAGRAPH_KEYS.every(
    (k) => paragraphs[k].status === "empty",
  );
  const anyLoading = PARAGRAPH_KEYS.some(
    (k) => paragraphs[k].status === "loading",
  );

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Compose cover letter
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Three short paragraphs based on the match analysis above.
            Tweak any of them, or click Try a different angle for a
            fresh take you can compare side-by-side.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ModelToggle
            value={model}
            onChange={setModel}
            disabled={draftMutation.isPending}
          />
          <Button
            size="sm"
            variant={noneStarted ? "primary" : "secondary"}
            onClick={composeAll}
            disabled={draftMutation.isPending || anyLoading}
          >
            {anyLoading ? (
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
      </div>

      <div className="mt-4 space-y-3">
        {PARAGRAPH_KEYS.map((key) => (
          <ParagraphCard
            key={key}
            label={PARAGRAPH_LABELS[key]}
            state={paragraphs[key]}
            onTweak={() => startTweak(key)}
            onCancel={() => cancelTweak(key)}
            onSave={() => saveTweak(key)}
            onEditChange={(v) => onEditChange(key, v)}
            onTryDifferent={() => tryDifferentAngle(key)}
            onUseAlternative={(i) => useAlternative(key, i)}
            onDiscardAlternative={(i) => discardAlternative(key, i)}
            onDiscardAll={() => discardAllAlternatives(key)}
            canTryDifferent={
              paragraphs[key].alternatives.length < MAX_ALTERNATIVES
            }
            onToggleHint={() => toggleHint(key)}
            onHintChange={(v) => onHintChange(key, v)}
            onApplyHint={() => applyHint(key)}
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

interface ParagraphCardProps {
  label: string;
  state: ParagraphState;
  onTweak: () => void;
  onCancel: () => void;
  onSave: () => void;
  onEditChange: (value: string) => void;
  onTryDifferent: () => void;
  onUseAlternative: (index: number) => void;
  onDiscardAlternative: (index: number) => void;
  onDiscardAll: () => void;
  canTryDifferent: boolean;
  onToggleHint: () => void;
  onHintChange: (value: string) => void;
  onApplyHint: () => void;
}

function ParagraphCard({
  label,
  state,
  onTweak,
  onCancel,
  onSave,
  onEditChange,
  onTryDifferent,
  onUseAlternative,
  onDiscardAlternative,
  onDiscardAll,
  canTryDifferent,
  onToggleHint,
  onHintChange,
  onApplyHint,
}: ParagraphCardProps) {
  const hasAlternatives = state.alternatives.length > 0;

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
          <div className="flex items-center gap-1.5">
            <Button
              size="sm"
              variant="ghost"
              onClick={onTryDifferent}
              disabled={!canTryDifferent || state.loadingAlternative}
              title={
                canTryDifferent
                  ? "Generate an alternative version with a different anchor"
                  : "Maximum alternatives reached. Use one or discard."
              }
            >
              {state.loadingAlternative ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Wand2 className="h-3.5 w-3.5" />
              )}
              Try a different angle
            </Button>
            <Button size="sm" variant="ghost" onClick={onTweak}>
              Tweak
            </Button>
          </div>
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

      {state.status === "viewing" && !hasAlternatives && (
        <p className="mt-2 text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">
          {state.text}
        </p>
      )}

      {/* Customize-this-paragraph (steering hint) — Phase 4.
          Available whenever the card has text, regardless of whether
          alternatives are open. The Apply action generates a new
          alternative steered by the hint, capped by the same
          MAX_ALTERNATIVES rule. */}
      {state.status === "viewing" && (
        <div className="mt-3">
          <button
            type="button"
            onClick={onToggleHint}
            className="text-[11px] text-slate-500 hover:text-slate-700 inline-flex items-center gap-1"
            disabled={!canTryDifferent || state.loadingAlternative}
            title={
              canTryDifferent
                ? "Steer the next alternative with a one-line direction"
                : "Maximum alternatives reached. Use one or discard."
            }
          >
            {state.hintOpen ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
            Customize this paragraph
          </button>

          {state.hintOpen && (
            <div className="mt-2 flex items-start gap-2">
              <input
                type="text"
                value={state.hintValue}
                onChange={(e) => onHintChange(e.target.value)}
                placeholder='e.g. "lead with the Everstream supply-chain ML work, not LLM stuff"'
                className="flex-1 text-xs text-slate-800 bg-white border border-slate-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-400/40 placeholder:text-slate-400"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && state.hintValue.trim()) {
                    onApplyHint();
                  }
                }}
                autoFocus
              />
              <Button
                size="sm"
                onClick={onApplyHint}
                disabled={
                  !state.hintValue.trim() ||
                  state.loadingAlternative ||
                  !canTryDifferent
                }
              >
                {state.loadingAlternative ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Send className="h-3.5 w-3.5" />
                )}
                Apply
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Side-by-side comparison view */}
      {state.status === "viewing" && hasAlternatives && (
        <div className="mt-2">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {/* Current */}
            <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1.5">
                Current
              </p>
              <p className="text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">
                {state.text}
              </p>
            </div>

            {/* Alternatives */}
            <div className="space-y-3">
              {state.alternatives.map((alt, i) => (
                <div
                  key={i}
                  className="rounded-md border border-indigo-200 bg-indigo-50/30 px-3 py-2"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-[10px] uppercase tracking-wide font-medium text-indigo-700">
                      Alternative {i + 1} of {state.alternatives.length}
                    </p>
                    <button
                      type="button"
                      onClick={() => onDiscardAlternative(i)}
                      className="text-slate-400 hover:text-slate-700"
                      title="Discard this alternative"
                      aria-label="Discard"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                  <p className="text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">
                    {alt}
                  </p>
                  <div className="mt-2 flex justify-end">
                    <Button
                      size="sm"
                      onClick={() => onUseAlternative(i)}
                      title="Use this version as the current paragraph"
                    >
                      Use this
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-2 flex justify-end">
            <button
              type="button"
              onClick={onDiscardAll}
              className="text-[11px] text-slate-500 hover:text-slate-700"
            >
              Discard all alternatives
            </button>
          </div>
        </div>
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
