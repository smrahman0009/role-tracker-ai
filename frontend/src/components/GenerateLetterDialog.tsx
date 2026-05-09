/**
 * GenerateLetterDialog — single dialog for the cover-letter Generate
 * button. Replaces both the old one-click Generate (which is now a
 * special case of "submit the dialog with empty fields") AND the
 * separate Refine dialog (which is now the "edit current draft" mode
 * inside this same dialog).
 *
 * See docs/cover_letter_dialog_plan.md for the design.
 */

import { useEffect, useState } from "react";

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
import { isDemoMode } from "@/lib/demoMode";
import { cn } from "@/lib/utils";

export interface GenerateDialogResult {
  mode: "scratch" | "edit";
  instruction: string;
  template: string;
  extended_thinking: boolean;
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Version number of the latest draft, if any. The "Edit current
   *  draft (vN)" radio is disabled when null. */
  currentVersion: number | null;
  /** True while either generate or refine is in flight. Disables
   *  the form and shows the spinner copy on the submit button. */
  isPending: boolean;
  onSubmit: (result: GenerateDialogResult) => void;
}

const MAX_INSTRUCTION = 500;
const MAX_TEMPLATE = 4_000;

export function GenerateLetterDialog({
  open,
  onOpenChange,
  currentVersion,
  isPending,
  onSubmit,
}: Props) {
  const canEdit = currentVersion !== null;
  const [mode, setMode] = useState<"scratch" | "edit">("scratch");
  const [instruction, setInstruction] = useState("");
  const [template, setTemplate] = useState("");
  const [extendedThinking, setExtendedThinking] = useState(false);

  // Reset form when the dialog opens. Each open starts fresh — too
  // easy to accidentally re-use stale guidance from a previous job.
  useEffect(() => {
    if (open) {
      setMode(canEdit ? "scratch" : "scratch");
      setInstruction("");
      setTemplate("");
      setExtendedThinking(false);
    }
  }, [canEdit, open]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isPending) return;

    // Edit mode requires non-empty instruction — that's the
    // "feedback" field the refine route needs.
    if (mode === "edit" && !instruction.trim()) {
      return;
    }
    onSubmit({
      mode,
      instruction: instruction.trim(),
      template: template.trim(),
      extended_thinking: extendedThinking,
    });
  };

  const submitLabel =
    mode === "edit"
      ? `Refine v${currentVersion}`
      : instruction || template
        ? "Generate"
        : "Generate (one-click)";

  const submitDisabled =
    isPending || (mode === "edit" && !instruction.trim());

  const inDemo = isDemoMode();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Generate cover letter</DialogTitle>
          <DialogDescription>
            All fields optional. Leave blank for a one-click draft, or
            steer the agent with instructions and a style template.
          </DialogDescription>
        </DialogHeader>
        {inDemo && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            <strong className="font-medium">Demo mode:</strong> instructions
            and template fields work for demonstration but aren't sent to
            an AI. Clicking Generate returns a pre-written sample letter so
            you can see the flow. In live mode, your instructions steer
            the agent.
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-slate-900">
              Mode
            </legend>
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="radio"
                name="mode"
                value="scratch"
                checked={mode === "scratch"}
                onChange={() => setMode("scratch")}
                className="mt-0.5"
              />
              <div className="text-sm">
                <div>Start from scratch</div>
                <div className="text-xs text-slate-400">
                  The agent reads your resume + JD and writes a fresh
                  letter.
                </div>
              </div>
            </label>
            <label
              className={cn(
                "flex items-start gap-2",
                canEdit
                  ? "cursor-pointer"
                  : "cursor-not-allowed opacity-50",
              )}
            >
              <input
                type="radio"
                name="mode"
                value="edit"
                checked={mode === "edit"}
                disabled={!canEdit}
                onChange={() => setMode("edit")}
                className="mt-0.5"
              />
              <div className="text-sm">
                <div>
                  Edit current draft
                  {canEdit ? ` (v${currentVersion})` : ""}
                </div>
                <div className="text-xs text-slate-400">
                  {canEdit
                    ? "Modify the latest version using your instructions as feedback. Preserves the strategy."
                    : "Generate a draft first, then this option becomes available."}
                </div>
              </div>
            </label>
          </fieldset>

          <div className="space-y-1.5">
            <Label htmlFor="instruction">
              Instructions{" "}
              <span className="font-normal text-slate-400">
                {mode === "edit" ? "(required)" : "(optional)"}
              </span>
            </Label>
            <textarea
              id="instruction"
              rows={3}
              maxLength={MAX_INSTRUCTION}
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:bg-slate-50"
              placeholder={
                mode === "edit"
                  ? "What should the agent change about v" +
                    (currentVersion ?? "?") +
                    "?"
                  : "Make it punchy, lead with the LLM project."
              }
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              disabled={isPending}
            />
            <div className="text-xs text-slate-400 text-right">
              {instruction.length} / {MAX_INSTRUCTION}
            </div>
          </div>

          {mode === "scratch" && (
            <div className="space-y-1.5">
              <Label htmlFor="template">
                Style template{" "}
                <span className="font-normal text-slate-400">
                  (optional, paste an existing letter to mirror its
                  voice)
                </span>
              </Label>
              <textarea
                id="template"
                rows={6}
                maxLength={MAX_TEMPLATE}
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:bg-slate-50"
                placeholder="Dear hiring manager, ..."
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
                disabled={isPending}
              />
              <div className="text-xs text-slate-400 text-right">
                {template.length} / {MAX_TEMPLATE}
              </div>
            </div>
          )}

          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={extendedThinking}
              onChange={(e) => setExtendedThinking(e.target.checked)}
              disabled={isPending}
              className="mt-0.5"
            />
            <div className="text-sm">
              <div>Extended thinking</div>
              <div className="text-xs text-slate-400">
                Slower, higher quality on non-obvious matches. ~3× cost.
              </div>
            </div>
          </label>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={submitDisabled}
            >
              {isPending ? "Working…" : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
