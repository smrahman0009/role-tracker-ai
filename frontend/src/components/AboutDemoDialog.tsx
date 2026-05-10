/**
 * AboutDemoDialog — disclaimer + author attribution shown when the
 * recruiter clicks the "About this demo" link in DemoBanner.
 *
 * Plain-English statement that the candidate, companies, and JDs are
 * fictional, plus two prominent links to the author's real GitHub and
 * LinkedIn.
 */

import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const AUTHOR_GITHUB = "https://github.com/smrahman0009";
const AUTHOR_LINKEDIN = "https://linkedin.com/in/mushfikurrahman";

export function AboutDemoDialog({ open, onOpenChange }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>About this demo</DialogTitle>
          <DialogDescription>
            Everything you see is fictional and pre-baked.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-sm text-slate-700">
          <p>
            The candidate <strong>Mahmud Karim</strong> is a fictional
            persona created for this walkthrough — not a real person.
            The resume, companies, job postings, salary bands, and
            cover letters are all original content written for the
            demo.
          </p>
          <p>
            No AI calls happen in demo mode. Clicking{" "}
            <em>Generate</em>, <em>Run analysis</em>, or{" "}
            <em>Polish</em> returns canned sample output so you can see
            the flow without spending tokens.
          </p>
          <p>
            In live mode, the same buttons run against your real
            resume and the real Anthropic API.
          </p>
          <p className="text-xs text-slate-500">
            Built by Shaikh Mushfikur Rahman as a portfolio project.
          </p>
        </div>

        <DialogFooter className="sm:justify-between gap-2">
          <Button
            variant="secondary"
            onClick={() => window.open(AUTHOR_GITHUB, "_blank", "noopener")}
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Author's GitHub
          </Button>
          <Button
            variant="secondary"
            onClick={() => window.open(AUTHOR_LINKEDIN, "_blank", "noopener")}
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Author's LinkedIn
          </Button>
          <Button variant="primary" onClick={() => onOpenChange(false)}>
            Got it
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
