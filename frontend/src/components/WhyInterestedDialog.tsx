/**
 * WhyInterestedDialog — generates a 2-3 sentence answer to the
 * "Why are you interested in this role?" screening question.
 *
 * Three actions on a generated answer:
 *   - Edit: the result is a textarea, you tweak words inline.
 *   - Polish: a single Haiku call fixes grammar / awkward phrasing
 *     in your edits without changing meaning or length.
 *   - Try again: regenerate from scratch (loses your edits).
 *
 * No persistence — closing the dialog discards everything. The cover
 * letter has versioning because it's worth iterating on; this is
 * 75 words, you copy and paste once.
 */

import { Check, Copy, Loader2, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Textarea, Label } from "@/components/ui/Input";
import { toast } from "@/components/ui/Toaster";
import {
  usePolishWhyInterested,
  useWhyInterested,
} from "@/hooks/useLetters";
import { cn } from "@/lib/utils";

const LENGTHS: Array<{ words: number; label: string; hint: string }> = [
  { words: 50, label: "Short", hint: "≈2 sentences" },
  { words: 75, label: "Medium", hint: "≈3 sentences" },
  { words: 120, label: "Long", hint: "≈4-5 sentences" },
];

interface WhyInterestedDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jobId: string;
}

export function WhyInterestedDialog({
  open,
  onOpenChange,
  jobId,
}: WhyInterestedDialogProps) {
  const [targetWords, setTargetWords] = useState(75);
  const [answer, setAnswer] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const generateMutation = useWhyInterested(jobId);
  const polishMutation = usePolishWhyInterested(jobId);

  const reset = () => {
    setAnswer(null);
    setCopied(false);
  };

  const generate = () => {
    setCopied(false);
    generateMutation.mutate(
      { target_words: targetWords },
      {
        onSuccess: (data) => setAnswer(data.text),
        onError: (err) => toast.error(`Generate failed: ${err.message}`),
      },
    );
  };

  const polish = () => {
    if (!answer || !answer.trim()) return;
    setCopied(false);
    polishMutation.mutate(answer, {
      onSuccess: (data) => {
        setAnswer(data.text);
        toast.success("Polished — meaning preserved");
      },
      onError: (err) => toast.error(`Polish failed: ${err.message}`),
    });
  };

  const copy = async () => {
    if (!answer) return;
    try {
      await navigator.clipboard.writeText(answer);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy — clipboard unavailable.");
    }
  };

  const wordCount = (answer ?? "").split(/\s+/).filter(Boolean).length;
  const isBusy = generateMutation.isPending || polishMutation.isPending;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-indigo-600" />
            "Why are you interested?"
          </DialogTitle>
          <DialogDescription>
            Drafts a tight, grounded answer for the screening question that
            shows up on most apply forms. Edit inline, polish for grammar,
            or regenerate from scratch.
          </DialogDescription>
        </DialogHeader>

        <div>
          <Label className="text-xs">Length</Label>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {LENGTHS.map((opt) => (
              <button
                key={opt.words}
                type="button"
                onClick={() => setTargetWords(opt.words)}
                disabled={isBusy}
                className={cn(
                  "rounded-lg border px-3 py-2 text-left transition-colors",
                  "focus:outline-none focus:ring-2 focus:ring-indigo-500/30",
                  targetWords === opt.words
                    ? "border-indigo-300 bg-indigo-50 text-indigo-900"
                    : "border-slate-200 hover:bg-slate-50 text-slate-700",
                  isBusy && "opacity-50 cursor-not-allowed",
                )}
              >
                <p className="text-sm font-medium">{opt.label}</p>
                <p className="text-[11px] text-slate-500">{opt.hint}</p>
              </button>
            ))}
          </div>
        </div>

        {answer != null && (
          <div className="space-y-2">
            <Textarea
              rows={6}
              value={answer}
              onChange={(e) => {
                setAnswer(e.target.value);
                setCopied(false);
              }}
              disabled={isBusy}
              className="text-sm leading-relaxed"
            />
            <div className="flex items-center justify-between text-[11px] text-slate-500">
              <span>{wordCount} words</span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={polish}
                  disabled={isBusy || !answer.trim()}
                  title="Fix grammar and clarity without changing meaning"
                  className={cn(
                    "inline-flex items-center gap-1 rounded px-2 py-1",
                    "hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30",
                    "disabled:opacity-50 disabled:cursor-not-allowed",
                  )}
                >
                  {polishMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Wand2 className="h-3.5 w-3.5" />
                  )}
                  {polishMutation.isPending ? "Polishing…" : "Polish"}
                </button>
                <button
                  type="button"
                  onClick={copy}
                  disabled={!answer.trim()}
                  className={cn(
                    "inline-flex items-center gap-1 rounded px-2 py-1",
                    "hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30",
                    "disabled:opacity-50 disabled:cursor-not-allowed",
                    copied && "text-emerald-600",
                  )}
                >
                  {copied ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="secondary"
            onClick={() => onOpenChange(false)}
            disabled={isBusy}
          >
            {answer ? "Done" : "Cancel"}
          </Button>
          <Button onClick={generate} disabled={isBusy}>
            {generateMutation.isPending ? (
              <Loader2 className="animate-spin" />
            ) : (
              <Sparkles />
            )}
            {generateMutation.isPending
              ? "Generating…"
              : answer
                ? "Try again"
                : "Generate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
