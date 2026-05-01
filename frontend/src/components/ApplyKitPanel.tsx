/**
 * ApplyKitPanel — read-only side panel that surfaces every piece of
 * data an employer's apply form will ask for, in copy-paste-ready
 * chunks. The user opens the employer page in a side window
 * (window.open with popup features), then clicks the clipboard icons
 * here to paste into the form. No browser automation — just friction
 * removal for manual applications.
 *
 * All data comes from existing hooks (useResume, useLetterVersions,
 * useProfile). This component owns no fetching.
 */

import {
  Check,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Mail,
  PanelRight,
  PictureInPicture2,
  Sparkles,
  X,
} from "lucide-react";
import { useState } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { toast } from "@/components/ui/Toaster";
import { LetterDownloadButton } from "@/components/LetterDownloadButton";
import { WhyInterestedDialog } from "@/components/WhyInterestedDialog";
import { useLetterVersions } from "@/hooks/useLetters";
import { usePictureInPictureWindow } from "@/hooks/usePictureInPictureWindow";
import { useProfile } from "@/hooks/useProfile";
import { useResume } from "@/hooks/useResume";
import { letterToPlainText } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Letter, ProfileResponse } from "@/lib/types";

interface ApplyKitPanelProps {
  userId: string;
  jobId: string;
  jobUrl: string;
}

export function ApplyKitPanel({ userId, jobId, jobUrl }: ApplyKitPanelProps) {
  const resumeQuery = useResume();
  const profileQuery = useProfile();
  const versionsQuery = useLetterVersions(jobId);
  const pip = usePictureInPictureWindow();
  const [whyOpen, setWhyOpen] = useState(false);

  const versions = versionsQuery.data?.versions ?? [];
  const sortedVersions = [...versions].sort((a, b) => b.version - a.version);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const currentLetter =
    sortedVersions.find((v) => v.version === selectedVersion) ??
    sortedVersions[0] ??
    null;

  const openPostingInSideWindow = () => {
    // Try popup first; if blocked, fall back to a new tab.
    const popup = window.open(
      jobUrl,
      "role-tracker-posting",
      "popup,width=720,height=900,resizable=yes,scrollbars=yes",
    );
    if (!popup) {
      window.open(jobUrl, "_blank", "noopener,noreferrer");
      toast(
        "Popup blocked — opened in a new tab. Allow popups for side-by-side apply.",
      );
    }
  };

  const openFloatingKit = async () => {
    const w = await pip.open({ width: 380, height: 900 });
    if (!w) {
      toast.error("Picture-in-picture isn't supported in this browser.");
      return;
    }
    if (w.document.title !== undefined) w.document.title = "Apply kit";
  };

  // The actual content lives in <ApplyKitBody />. When the PiP window is
  // open, we render a placeholder card here and portal the body into the
  // floating window instead. React context (auth, query cache) propagates
  // across the portal automatically since it's the same React tree.
  const body = (
    <ApplyKitBody
      userId={userId}
      jobId={jobId}
      onOpenPosting={openPostingInSideWindow}
      onOpenWhy={() => setWhyOpen(true)}
      resume={resumeQuery.data}
      profile={profileQuery.data}
      versions={sortedVersions}
      currentLetter={currentLetter}
      isLetterLoading={versionsQuery.isLoading}
      onSelectVersion={setSelectedVersion}
      isFloating={!!pip.pipWindow}
      isPipSupported={pip.isSupported}
      onOpenFloating={openFloatingKit}
      onCloseFloating={pip.close}
    />
  );

  if (pip.pipWindow) {
    return (
      <>
        <FloatingPlaceholder onBringBack={pip.close} />
        {createPortal(
          <div className="p-4 max-w-md mx-auto">{body}</div>,
          pip.pipWindow.document.body,
        )}
        <WhyInterestedDialog
          open={whyOpen}
          onOpenChange={setWhyOpen}
          jobId={jobId}
        />
      </>
    );
  }

  return (
    <>
      {body}
      <WhyInterestedDialog
        open={whyOpen}
        onOpenChange={setWhyOpen}
        jobId={jobId}
      />
    </>
  );
}

function FloatingPlaceholder({ onBringBack }: { onBringBack: () => void }) {
  return (
    <Card className="border-dashed">
      <CardContent className="py-5 text-center">
        <PictureInPicture2 className="h-5 w-5 text-indigo-500 mx-auto" />
        <p className="text-sm font-medium text-slate-900 mt-2">
          Apply kit is floating
        </p>
        <p className="text-[11px] text-slate-500 mt-1 max-w-[240px] mx-auto">
          The kit is in its own always-on-top window. Drag it next to the
          employer's apply page.
        </p>
        <Button
          variant="ghost"
          size="sm"
          onClick={onBringBack}
          className="mt-3"
        >
          <X />
          Bring back
        </Button>
      </CardContent>
    </Card>
  );
}

interface ApplyKitBodyProps {
  userId: string;
  jobId: string;
  onOpenPosting: () => void;
  onOpenWhy: () => void;
  resume: import("@/lib/types").ResumeMetadata | null | undefined;
  profile: ProfileResponse | undefined;
  versions: Letter[];
  currentLetter: Letter | null;
  isLetterLoading: boolean;
  onSelectVersion: (v: number) => void;
  isFloating: boolean;
  isPipSupported: boolean;
  onOpenFloating: () => void;
  onCloseFloating: () => void;
}

function ApplyKitBody({
  userId,
  jobId,
  onOpenPosting,
  onOpenWhy,
  resume,
  profile,
  versions,
  currentLetter,
  isLetterLoading,
  onSelectVersion,
  isFloating,
  isPipSupported,
  onOpenFloating,
  onCloseFloating,
}: ApplyKitBodyProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <PanelRight className="h-4 w-4 text-indigo-600" />
          Apply kit
        </CardTitle>
        {isPipSupported && (
          <button
            type="button"
            onClick={isFloating ? onCloseFloating : onOpenFloating}
            className="text-[11px] text-slate-500 hover:text-slate-900 inline-flex items-center gap-1"
            title={
              isFloating
                ? "Close the floating window"
                : "Open as a floating, always-on-top window (Chrome/Edge)"
            }
          >
            <PictureInPicture2 className="h-3 w-3" />
            {isFloating ? "Dock" : "Float"}
          </button>
        )}
      </CardHeader>
      <CardContent className="space-y-5">
        <Button onClick={onOpenPosting} className="w-full" variant="primary">
          <ExternalLink />
          Open posting in side window
        </Button>
        <p className="-mt-3 text-[11px] text-slate-500 leading-relaxed">
          Opens the employer's apply page beside this one. Paste from the
          fields below into their form.
        </p>

        <Button
          onClick={onOpenWhy}
          variant="secondary"
          className="w-full"
          title="Generate a 2-3 sentence answer for the apply form's screening question"
        >
          <Sparkles />
          Draft "Why are you interested?"
        </Button>

        <ResumeBlock userId={userId} resume={resume} />
        <CoverLetterBlock
          userId={userId}
          jobId={jobId}
          versions={versions}
          current={currentLetter}
          isLoading={isLetterLoading}
          onSelectVersion={onSelectVersion}
        />
        <ProfileBlock profile={profile} />
      </CardContent>
    </Card>
  );
}

// ---------- Resume ----------

function ResumeBlock({
  userId,
  resume,
}: {
  userId: string;
  resume: import("@/lib/types").ResumeMetadata | null | undefined;
}) {
  return (
    <Section
      icon={<FileText className="h-3.5 w-3.5" />}
      title="Resume"
      empty={!resume}
      emptyText="No resume uploaded. Add one in Settings."
    >
      {resume && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 flex items-center gap-2">
          <p className="text-xs font-medium text-slate-900 truncate flex-1">
            {resume.filename}
          </p>
          <Button asChild size="sm" variant="ghost">
            <a
              href={`/api/users/${encodeURIComponent(userId)}/resume/file`}
              target="_blank"
              rel="noopener noreferrer"
              title="Open resume"
            >
              <Download />
            </a>
          </Button>
        </div>
      )}
    </Section>
  );
}

// ---------- Cover letter ----------

function CoverLetterBlock({
  userId,
  jobId,
  versions,
  current,
  isLoading,
  onSelectVersion,
}: {
  userId: string;
  jobId: string;
  versions: Letter[];
  current: Letter | null;
  isLoading: boolean;
  onSelectVersion: (v: number) => void;
}) {
  return (
    <Section
      icon={<Mail className="h-3.5 w-3.5" />}
      title="Cover letter"
      empty={!isLoading && !current}
      emptyText="Generate a letter on the left to make it available here."
    >
      {current && (
        <>
          {versions.length > 1 && (
            <select
              value={current.version}
              onChange={(e) => onSelectVersion(Number(e.target.value))}
              className="text-xs font-medium rounded border border-slate-200 bg-white px-2 py-1 mb-2 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            >
              {versions.map((v) => (
                <option key={v.version} value={v.version}>
                  v{v.version}
                  {v.refinement_index > 0 ? ` · refine #${v.refinement_index}` : ""}
                  {v.edited_by_user ? " · edited" : ""}
                </option>
              ))}
            </select>
          )}
          <div className="flex gap-2">
            <CopyButton
              value={letterToPlainText(current.text)}
              label="Copy text"
              size="full"
            />
            <LetterDownloadButton
              userId={userId}
              jobId={jobId}
              version={current.version}
              iconOnly
            />
          </div>
          <p className="text-[11px] text-slate-500">
            {current.word_count} words · v{current.version}
          </p>
        </>
      )}
    </Section>
  );
}

// ---------- Profile fields ----------

const PROFILE_ROWS: Array<{
  key: keyof ProfileResponse;
  label: string;
}> = [
  { key: "name", label: "Name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "city", label: "Location" },
  { key: "linkedin_url", label: "LinkedIn" },
  { key: "github_url", label: "GitHub" },
  { key: "portfolio_url", label: "Portfolio" },
];

function ProfileBlock({
  profile,
}: {
  profile: ProfileResponse | undefined;
}) {
  const populatedRows = profile
    ? PROFILE_ROWS.filter((r) => {
        const v = profile[r.key];
        return typeof v === "string" && v.trim().length > 0;
      })
    : [];

  return (
    <Section
      icon={<Copy className="h-3.5 w-3.5" />}
      title="Quick fields"
      empty={populatedRows.length === 0}
      emptyText="Fill out your contact info in Settings to copy from here."
    >
      {populatedRows.length > 0 && (
        <div className="space-y-1">
          {populatedRows.map((r) => (
            <ProfileRow
              key={r.key}
              label={r.label}
              value={String(profile?.[r.key] ?? "")}
            />
          ))}
        </div>
      )}
    </Section>
  );
}

function ProfileRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2 group">
      <span className="text-[10px] uppercase tracking-wide font-medium text-slate-500 w-16 shrink-0">
        {label}
      </span>
      <span className="text-xs text-slate-800 flex-1 truncate" title={value}>
        {value}
      </span>
      <CopyButton value={value} />
    </div>
  );
}

// ---------- shared ----------

function Section({
  icon,
  title,
  empty,
  emptyText,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  empty: boolean;
  emptyText: string;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <p className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide font-medium text-slate-500 mb-2">
        {icon}
        {title}
      </p>
      {empty ? (
        <p className="text-[11px] text-slate-400 italic">{emptyText}</p>
      ) : (
        <div className="space-y-2">{children}</div>
      )}
    </div>
  );
}

function CopyButton({
  value,
  label,
  size = "icon",
}: {
  value: string;
  label?: string;
  size?: "icon" | "full";
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy — clipboard unavailable.");
    }
  };

  if (size === "full") {
    return (
      <Button
        size="sm"
        variant="secondary"
        onClick={copy}
        className="flex-1"
      >
        {copied ? <Check className="text-emerald-600" /> : <Copy />}
        {copied ? "Copied" : (label ?? "Copy")}
      </Button>
    );
  }

  return (
    <button
      type="button"
      onClick={copy}
      className={cn(
        "rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700",
        "transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500/30",
        copied && "text-emerald-600 hover:text-emerald-700",
      )}
      aria-label={`Copy ${label ?? "value"}`}
      title="Copy"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}
