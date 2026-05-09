/**
 * WhyInterestedDialog — grammar / clarity polish for the
 * "Why are you interested in this role?" answer the user typed
 * into an apply form.
 *
 * The previous version of this dialog generated a finished 2-3
 * sentence motivation paragraph from the resume + JD. That
 * generator was removed in May 2026 because the output looked
 * authentic but wasn't, and "why are you interested?" is the
 * one recruiter question specifically about authenticity. See
 * docs/HANDBOOK.md for the design rationale.
 *
 * What's left: paste your own answer, click Polish, get back a
 * grammar-cleaned version with the same meaning, length, and
 * voice. Single Haiku call (~$0.005, ~3s).
 */

import { Check, Copy, Loader2, Wand2 } from "lucide-react";
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
import { Label, Textarea } from "@/components/ui/Input";
import { toast } from "@/components/ui/Toaster";
import { usePolishWhyInterested } from "@/hooks/useLetters";
import { cn } from "@/lib/utils";

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
  const [answer, setAnswer] = useState("");
  const [copied, setCopied] = useState(false);
  const polishMutation = usePolishWhyInterested(jobId);

  const reset = () => {
    setAnswer("");
    setCopied(false);
  };

  const polish = () => {
    if (!answer.trim()) return;
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
    if (!answer.trim()) return;
    try {
      await navigator.clipboard.writeText(answer);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy — clipboard unavailable.");
    }
  };

  const wordCount = answer.split(/\s+/).filter(Boolean).length;
  const isBusy = polishMutation.isPending;

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
          <DialogTitle>"Why are you interested?" — grammar fix</DialogTitle>
          <DialogDescription>
            Paste the answer you wrote into the apply form. Click
            Polish to fix grammar and clarity without changing
            meaning, length, or voice.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="why-interested-answer" className="text-xs">
            Your answer
          </Label>
          <Textarea
            id="why-interested-answer"
            rows={6}
            value={answer}
            placeholder="Paste your answer here…"
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

        <DialogFooter>
          <Button
            variant="secondary"
            onClick={() => onOpenChange(false)}
            disabled={isBusy}
          >
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
