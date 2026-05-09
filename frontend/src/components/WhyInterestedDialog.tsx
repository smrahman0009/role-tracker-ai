/**
 * WhyInterestedDialog — grammar / clarity polish for the
 * "Why are you interested in this role?" answer the user typed
 * into an apply form.
 *
 * Two render modes:
 *
 *   - Main window: full Radix Dialog with focus trap, modal overlay,
 *     and a controlled textarea backed by React state.
 *
 *   - Picture-in-Picture window (detected via PortalContainerContext):
 *     a non-modal inline panel using an UNCONTROLLED textarea (ref
 *     + defaultValue), and a clipboard call that targets the PiP
 *     window's navigator.
 *
 * Why the split: React 19 + Radix UI + Document Picture-in-Picture
 * has two known limitations:
 *
 *   1. Controlled inputs lose change events across the document
 *      boundary (React's event delegation runs in the main document
 *      and never sees events from the PiP DOM). Result: the first
 *      keystroke types, then React resets the textarea to its empty
 *      state on the next render, the cursor goes weird, and typing
 *      becomes broken.
 *
 *   2. Radix's focus trap inside Dialog assumes single-document
 *      reality and fights with the PiP window's native focus
 *      management.
 *
 * The PiP-only path uses uncontrolled inputs (no React reconciliation
 * resetting the value) and skips Radix Dialog's focus trap. Both
 * sidestepped, both bugs gone.
 *
 * The Polish API call still works — Polish reads the textarea's
 * current value on click, sends it to the backend, and writes the
 * polished result back into the textarea via ref.
 */

import { Check, Copy, Loader2, Wand2, X } from "lucide-react";
import { useRef, useState } from "react";

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
import {
  usePortalContainer,
  writeToClipboard,
} from "@/lib/portalContainer";
import { cn } from "@/lib/utils";

interface WhyInterestedDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jobId: string;
}

export function WhyInterestedDialog(props: WhyInterestedDialogProps) {
  const portalContainer = usePortalContainer();
  // PortalContainerContext is only set inside the PiP wrapper, so this
  // is a reliable "are we in PiP?" signal.
  const isInPip = Boolean(portalContainer);
  return isInPip ? (
    <WhyInterestedPipPanel {...props} pipContainer={portalContainer!} />
  ) : (
    <WhyInterestedModalDialog {...props} />
  );
}


// ----- Main window: Radix Dialog with controlled textarea ---------------


function WhyInterestedModalDialog({
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
      await writeToClipboard(answer);
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
          <ToolbarRow
            wordCount={wordCount}
            isPolishPending={polishMutation.isPending}
            onPolish={polish}
            onCopy={copy}
            polishDisabled={isBusy || !answer.trim()}
            copyDisabled={!answer.trim()}
            copied={copied}
          />
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


// ----- PiP window: inline non-modal panel, uncontrolled textarea --------


function WhyInterestedPipPanel({
  open,
  onOpenChange,
  jobId,
  pipContainer,
}: WhyInterestedDialogProps & { pipContainer: HTMLElement }) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [copied, setCopied] = useState(false);
  // Word-count is derived imperatively from the ref on each interaction
  // (no controlled state). Tracking via a state that the user-facing
  // count cells read, updated only on input, is fine because that
  // state's value is never written back into the textarea.
  const [wordCount, setWordCount] = useState(0);
  const polishMutation = usePolishWhyInterested(jobId);

  const reset = () => {
    if (textareaRef.current) textareaRef.current.value = "";
    setCopied(false);
    setWordCount(0);
  };

  const updateWordCount = () => {
    const value = textareaRef.current?.value ?? "";
    setWordCount(value.split(/\s+/).filter(Boolean).length);
  };

  const currentText = () => textareaRef.current?.value.trim() ?? "";

  const polish = () => {
    const text = currentText();
    if (!text) return;
    setCopied(false);
    polishMutation.mutate(text, {
      onSuccess: (data) => {
        if (textareaRef.current) textareaRef.current.value = data.text;
        updateWordCount();
        toast.success("Polished — meaning preserved");
      },
      onError: (err) => toast.error(`Polish failed: ${err.message}`),
    });
  };

  const copy = async () => {
    const text = currentText();
    if (!text) return;
    try {
      await writeToClipboard(text, pipContainer);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy — clipboard unavailable.");
    }
  };

  const handleClose = () => {
    onOpenChange(false);
    reset();
  };

  if (!open) return null;

  const isBusy = polishMutation.isPending;

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-start justify-center px-3 py-6",
        "bg-slate-900/40 backdrop-blur-sm overflow-y-auto",
      )}
      onClick={(e) => {
        // Click outside the inner card closes the panel — same UX as
        // the Dialog overlay click-to-dismiss.
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        className={cn(
          "w-full max-w-md rounded-xl bg-white border border-slate-200",
          "shadow-md p-6 relative",
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={handleClose}
          className="absolute right-4 top-4 rounded p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="mb-4 space-y-1.5">
          <h2 className="text-base font-semibold text-slate-900">
            "Why are you interested?" — grammar fix
          </h2>
          <p className="text-xs text-slate-500">
            Paste the answer you wrote into the apply form. Click
            Polish to fix grammar and clarity without changing
            meaning, length, or voice.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="why-interested-pip-answer" className="text-xs">
            Your answer
          </Label>
          {/* Uncontrolled — defaultValue + ref. React doesn't reconcile
              the value, so the cross-document portal event-delegation
              issue can't break typing here. */}
          <textarea
            id="why-interested-pip-answer"
            ref={textareaRef}
            rows={6}
            defaultValue=""
            placeholder="Paste your answer here…"
            disabled={isBusy}
            onInput={updateWordCount}
            onChange={() => setCopied(false)}
            className={cn(
              "w-full rounded-md border border-slate-200 px-3 py-2",
              "text-sm leading-relaxed",
              "focus:outline-none focus:ring-2 focus:ring-indigo-500/20",
              "disabled:bg-slate-50 disabled:cursor-not-allowed",
            )}
          />
          <ToolbarRow
            wordCount={wordCount}
            isPolishPending={polishMutation.isPending}
            onPolish={polish}
            onCopy={copy}
            polishDisabled={isBusy || wordCount === 0}
            copyDisabled={wordCount === 0}
            copied={copied}
          />
        </div>

        <div className="mt-4 flex justify-end">
          <Button
            variant="secondary"
            onClick={handleClose}
            disabled={isBusy}
          >
            Done
          </Button>
        </div>
      </div>
    </div>
  );
}


// ----- Shared toolbar (Polish + Copy + word count) ----------------------


function ToolbarRow({
  wordCount,
  isPolishPending,
  onPolish,
  onCopy,
  polishDisabled,
  copyDisabled,
  copied,
}: {
  wordCount: number;
  isPolishPending: boolean;
  onPolish: () => void;
  onCopy: () => void;
  polishDisabled: boolean;
  copyDisabled: boolean;
  copied: boolean;
}) {
  return (
    <div className="flex items-center justify-between text-[11px] text-slate-500">
      <span>{wordCount} words</span>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onPolish}
          disabled={polishDisabled}
          title="Fix grammar and clarity without changing meaning"
          className={cn(
            "inline-flex items-center gap-1 rounded px-2 py-1",
            "hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          {isPolishPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Wand2 className="h-3.5 w-3.5" />
          )}
          {isPolishPending ? "Polishing…" : "Polish"}
        </button>
        <button
          type="button"
          onClick={onCopy}
          disabled={copyDisabled}
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
  );
}
