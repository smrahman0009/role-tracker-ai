/**
 * DemoBanner — thin yellow strip rendered at the top of the layout
 * whenever the user is in demo mode.
 *
 * Always visible — no dismiss. Demo mode is a persistent state, and
 * the banner is the recruiter's running reminder that they're not
 * looking at a real account. "Exit demo" sends them back to the
 * login page where they can sign in for real.
 */

import { Info, Sparkles } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { useAuth } from "@/auth/AuthContext";
import { AboutDemoDialog } from "@/components/AboutDemoDialog";
import { exitDemoMode, isDemoMode } from "@/lib/demoMode";

export function DemoBanner() {
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const [aboutOpen, setAboutOpen] = useState(false);
  if (!isDemoMode()) return null;

  const handleExit = () => {
    exitDemoMode();
    signOut();
    navigate("/login", { replace: true });
  };

  return (
    <>
      <div className="bg-amber-50 border-b border-amber-200 px-4 py-2">
        <div className="max-w-5xl mx-auto flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 text-amber-900">
            <Sparkles className="h-3.5 w-3.5 text-amber-600" />
            <span>
              <strong className="font-medium">Demo mode</strong> — actions
              return sample data, no AI calls happen, nothing is saved.
            </span>
            <button
              type="button"
              onClick={() => setAboutOpen(true)}
              className="inline-flex items-center gap-1 text-amber-900 underline-offset-2 hover:underline"
            >
              <Info className="h-3 w-3" />
              About this demo
            </button>
          </div>
          <button
            type="button"
            onClick={handleExit}
            className="text-amber-900 font-medium underline-offset-2 hover:underline whitespace-nowrap"
          >
            Sign in for real account →
          </button>
        </div>
      </div>
      <AboutDemoDialog open={aboutOpen} onOpenChange={setAboutOpen} />
    </>
  );
}
