/**
 * WhyInterestedDialog — helps the user answer the "Why are you
 * interested in this role?" screening question.
 *
 * Two operations, both single Haiku calls:
 *
 *   - "Show JD highlights" — surfaces 4-5 short factual bullets about
 *     what's distinctive in the job description. The bullets are
 *     research material; the AI does NOT receive the user's resume
 *     and is NOT writing the answer for them.
 *
 *   - "Polish" — fixes grammar / clarity in whatever the user types
 *     in the textarea below. Defensible AI assist (copy-edit, not
 *     ghostwrite).
 *
 * Design rationale: the previous version of this dialog generated a
 * full motivation paragraph using the resume + JD. That output looked
 * authentic but wasn't — and "why are you interested?" is the one
 * recruiter question specifically about authenticity. Removed in
 * May 2026 in favour of this research-helper framing.
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
import { Label, Textarea } from "@/components/ui/Input";
import { toast } from "@/components/ui/Toaster";
import {
  usePolishWhyInterested,
  useWhyInterestedHighlights,
} from "@/hooks/useLetters";
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
  const [highlights, setHighlights] = useState<string[] | null>(null);
  const [answer, setAnswer] = useState("");
  const [copied, setCopied] = useState(false);

  const highlightsMutation = useWhyInterestedHighlights(jobId);
  const polishMutation = usePolishWhyInterested(jobId);

  const reset = () => {
    setHighlights(null);
    setAnswer("");
    setCopied(false);
  };

  const showHighlights = () => {
    highlightsMutation.mutate(undefined, {
      onSuccess: (data) => setHighlights(data.highlights),
      onError: (err) => toast.error(`Failed: ${err.message}`),
    });
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
  const isBusy =
    highlightsMutation.isPending || polishMutation.isPending;

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
            Surface what's distinctive in the JD as research material,
            then write your own honest answer below. Polish fixes
            grammar without changing meaning.
          </DialogDescription>
        </DialogHeader>

        {/* Highlights panel — research material, not a draft answer. */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-xs">JD highlights</Label>
            <button
              type="button"
              onClick={showHighlights}
              disabled={isBusy}
              className={cn(
                "inline-flex items-center gap-1 rounded px-2 py-1 text-xs",
                "text-indigo-700 hover:bg-indigo-50",
                "focus:outline-none focus:ring-2 focus:ring-indigo-500/30",
                "disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            >
              {highlightsMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              {highlightsMutation.isPending
                ? "Reading the JD…"
                : highlights
                  ? "Refresh highlights"
                  : "Show highlights"}
            </button>
          </div>

          {highlights == null ? (
            <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
              Click <em>Show highlights</em> to see 4–5 short bullets
              about what's distinctive in this role and company. Use
              them as a starting point — pick what genuinely interests
              you and write about that below.
            </p>
          ) : highlights.length === 0 ? (
            <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
              The model didn't find anything especially distinctive
              about this JD. You're on your own for this one — write
              from your own knowledge of the company.
            </p>
          ) : (
            <ul className="space-y-1 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-800">
              {highlights.map((h, i) => (
                <li
                  key={i}
                  className="leading-relaxed before:mr-2 before:content-['•'] before:text-indigo-500"
                >
                  {h}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* User's own answer — they type here. */}
        <div className="space-y-2">
          <Label htmlFor="why-interested-answer" className="text-xs">
            Your answer
          </Label>
          <Textarea
            id="why-interested-answer"
            rows={6}
            value={answer}
            placeholder="In your own words: what specifically about this role and what you've done makes this a fit? Use the highlights above as research, not a script."
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
