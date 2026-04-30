/**
 * WhyInterestedDialog — generates a 2-3 sentence answer to the
 * "Why are you interested in this role?" screening question that shows
 * up on almost every apply form. Single Claude Haiku call (~5s, ~$0.01).
 *
 * Flow: user picks a target length, clicks Generate, sees the answer,
 * clicks Copy, pastes into the employer's form. Can regenerate if the
 * first take isn't right.
 */

import { Check, Copy, Loader2, Sparkles } from "lucide-react";
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
import { Label } from "@/components/ui/Input";
import { toast } from "@/components/ui/Toaster";
import { useWhyInterested } from "@/hooks/useLetters";
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
  const mutation = useWhyInterested(jobId);

  const reset = () => {
    setAnswer(null);
    setCopied(false);
  };

  const generate = () => {
    setCopied(false);
    mutation.mutate(
      { target_words: targetWords },
      {
        onSuccess: (data) => setAnswer(data.text),
        onError: (err) => toast.error(`Generate failed: ${err.message}`),
      },
    );
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
            shows up on most apply forms. Uses your resume + this job's
            description.
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
                disabled={mutation.isPending}
                className={cn(
                  "rounded-lg border px-3 py-2 text-left transition-colors",
                  "focus:outline-none focus:ring-2 focus:ring-indigo-500/30",
                  targetWords === opt.words
                    ? "border-indigo-300 bg-indigo-50 text-indigo-900"
                    : "border-slate-200 hover:bg-slate-50 text-slate-700",
                  mutation.isPending && "opacity-50 cursor-not-allowed",
                )}
              >
                <p className="text-sm font-medium">{opt.label}</p>
                <p className="text-[11px] text-slate-500">{opt.hint}</p>
              </button>
            ))}
          </div>
        </div>

        {answer && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
              {answer}
            </p>
            <div className="flex items-center justify-between mt-2 text-[11px] text-slate-500">
              <span>{answer.split(/\s+/).filter(Boolean).length} words</span>
              <button
                type="button"
                onClick={copy}
                className={cn(
                  "inline-flex items-center gap-1 rounded px-2 py-1",
                  "hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30",
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
        )}

        <DialogFooter>
          <Button
            variant="secondary"
            onClick={() => onOpenChange(false)}
            disabled={mutation.isPending}
          >
            {answer ? "Done" : "Cancel"}
          </Button>
          <Button onClick={generate} disabled={mutation.isPending}>
            {mutation.isPending ? (
              <Loader2 className="animate-spin" />
            ) : (
              <Sparkles />
            )}
            {mutation.isPending
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
