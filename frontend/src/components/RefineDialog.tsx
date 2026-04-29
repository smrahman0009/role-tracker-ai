/**
 * RefineDialog — modal that captures freeform feedback and kicks off a
 * refine generation. The page handles polling and version invalidation;
 * we just collect the feedback string and submit.
 */

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
import { Textarea } from "@/components/ui/Input";

interface RefineDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  remaining: number;
  isSubmitting: boolean;
  onSubmit: (feedback: string) => void;
}

export function RefineDialog({
  open,
  onOpenChange,
  remaining,
  isSubmitting,
  onSubmit,
}: RefineDialogProps) {
  const [feedback, setFeedback] = useState("");

  const submit = () => {
    const v = feedback.trim();
    if (!v) return;
    onSubmit(v);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) setFeedback("");
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Refine letter</DialogTitle>
          <DialogDescription>
            Tell the agent what to change. It will revise the current
            version and produce a new one. {remaining} of 10 refinements
            left for this letter.
          </DialogDescription>
        </DialogHeader>
        <Textarea
          rows={5}
          autoFocus
          placeholder="e.g. The opening paragraph is too generic — anchor it on the McKesson supply-chain project instead."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          disabled={isSubmitting}
        />
        <DialogFooter>
          <Button
            variant="secondary"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            onClick={submit}
            disabled={isSubmitting || !feedback.trim() || remaining <= 0}
          >
            {isSubmitting ? "Refining…" : "Refine"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
