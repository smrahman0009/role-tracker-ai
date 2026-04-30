/**
 * OnboardingChecklist — three-step "set yourself up" banner for new
 * users on the home page. Hides once all three steps are done.
 *
 * Steps:
 *   1. Upload resume (resume metadata exists)
 *   2. Add contact info (profile.name + at least email or phone)
 *   3. Run your first search (last_refreshed_at on the snapshot is set)
 *
 * The banner is also dismissible — once dismissed it stays hidden via
 * localStorage, even if the user later removes their resume etc. That's
 * intentional: the banner is for orientation, not nagging.
 */

import { Check, Circle, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { useProfile } from "@/hooks/useProfile";
import { useResume } from "@/hooks/useResume";
import { cn } from "@/lib/utils";

const DISMISSED_KEY = "role-tracker.onboarding-dismissed";

export function OnboardingChecklist({
  hasSearched,
  onJumpToSearch,
}: {
  hasSearched: boolean;
  onJumpToSearch: () => void;
}) {
  const resume = useResume();
  const profile = useProfile();
  const [dismissed, setDismissed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(DISMISSED_KEY) === "1";
    } catch {
      return false;
    }
  });

  const hasResume = !!resume.data;
  const hasContact = Boolean(
    profile.data?.name?.trim() &&
      (profile.data.email?.trim() || profile.data.phone?.trim()),
  );

  const allDone = hasResume && hasContact && hasSearched;

  if (allDone || dismissed) return null;

  const dismiss = () => {
    setDismissed(true);
    try {
      localStorage.setItem(DISMISSED_KEY, "1");
    } catch {
      // ignore
    }
  };

  return (
    <Card className="border-indigo-200 bg-indigo-50/40">
      <CardContent className="py-4 px-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">
              Get set up
            </p>
            <p className="text-xs text-slate-600 mt-0.5">
              Three quick steps and you're searching jobs ranked against your
              resume.
            </p>
          </div>
          <button
            type="button"
            onClick={dismiss}
            className="text-slate-400 hover:text-slate-700 -mt-1 -mr-1 p-1"
            title="Dismiss for now"
            aria-label="Dismiss checklist"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <ul className="mt-3 space-y-1.5">
          <Step
            done={hasResume}
            label="Upload your resume"
            action={
              !hasResume ? (
                <span className="text-[11px] text-slate-500">
                  use the card above
                </span>
              ) : null
            }
          />
          <Step
            done={hasContact}
            label="Add contact info"
            action={
              !hasContact ? (
                <Button asChild variant="ghost" size="sm">
                  <Link to="/settings">Settings →</Link>
                </Button>
              ) : null
            }
          />
          <Step
            done={hasSearched}
            label="Run your first search"
            action={
              hasResume && !hasSearched ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onJumpToSearch}
                >
                  Jump to form →
                </Button>
              ) : null
            }
          />
        </ul>
      </CardContent>
    </Card>
  );
}

function Step({
  done,
  label,
  action,
}: {
  done: boolean;
  label: string;
  action?: React.ReactNode;
}) {
  return (
    <li className="flex items-center gap-2 text-xs">
      {done ? (
        <Check className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
      ) : (
        <Circle className="h-3.5 w-3.5 text-slate-400 shrink-0" />
      )}
      <span
        className={cn(
          "flex-1",
          done ? "text-slate-500 line-through" : "text-slate-800",
        )}
      >
        {label}
      </span>
      {action}
    </li>
  );
}
