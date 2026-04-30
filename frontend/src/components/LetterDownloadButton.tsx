/**
 * LetterDownloadButton — small dropdown that picks PDF or DOCX before
 * downloading. Used on the Job Detail letter workspace and the Apply
 * Kit. Defers the actual download to a hidden anchor click so the
 * Content-Disposition header from the backend drives the filename.
 */

import { ChevronDown, Download, FileText } from "lucide-react";

import { Button } from "@/components/ui/Button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { letterDownloadUrl } from "@/hooks/useLetters";
import { cn } from "@/lib/utils";

interface Props {
  userId: string;
  jobId: string;
  version: number;
  /** Render as the icon-only variant (used in the cramped letter workspace). */
  iconOnly?: boolean;
}

export function LetterDownloadButton({
  userId,
  jobId,
  version,
  iconOnly = false,
}: Props) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant={iconOnly ? "ghost" : "secondary"}
          size="sm"
          title="Download letter"
        >
          <Download />
          {!iconOnly && (
            <>
              Download
              <ChevronDown className="opacity-60" />
            </>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-44 p-1" align="end">
        <DownloadOption
          href={letterDownloadUrl(userId, jobId, version, "pdf")}
          label="PDF"
          hint="Universal"
        />
        <DownloadOption
          href={letterDownloadUrl(userId, jobId, version, "docx")}
          label="Word (.docx)"
          hint="Best for ATS"
        />
      </PopoverContent>
    </Popover>
  );
}

function DownloadOption({
  href,
  label,
  hint,
}: {
  href: string;
  label: string;
  hint: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "flex items-center justify-between gap-2 rounded px-2 py-1.5",
        "text-xs text-slate-700 hover:bg-slate-100",
        "focus:outline-none focus:bg-slate-100",
      )}
    >
      <span className="inline-flex items-center gap-2">
        <FileText className="h-3.5 w-3.5 text-slate-500" />
        {label}
      </span>
      <span className="text-[10px] text-slate-500">{hint}</span>
    </a>
  );
}
