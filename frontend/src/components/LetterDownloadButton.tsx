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
import { toast } from "@/components/ui/Toaster";
import { api } from "@/lib/api";
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
  // Both formats go through fetch (api.raw injects the bearer token);
  // a plain <a href> would navigate without the Authorization header
  // and the middleware would 401. The bytes land on disk via a blob
  // URL + dynamic anchor click — same trick the browser would do
  // natively if downloads were public.
  const downloadPdf = async () => {
    try {
      const path = `/users/${userId}/jobs/${jobId}/letters/${version}/download.pdf`;
      const response = await api.raw(path);
      const pages = Number(response.headers.get("X-Letter-Pages") ?? "1");
      const blob = await response.blob();
      saveBlob(blob, `cover_letter_v${version}.pdf`);
      if (Number.isFinite(pages) && pages > 1) {
        toast(
          `Heads up: this letter prints to ${pages} pages. Consider shortening the body before sending.`,
          { duration: 8000 },
        );
      }
    } catch (err) {
      toast.error(`Download failed: ${(err as Error).message}`);
    }
  };

  const downloadDocx = async () => {
    try {
      const path = `/users/${userId}/jobs/${jobId}/letters/${version}/download.docx`;
      const response = await api.raw(path);
      const blob = await response.blob();
      saveBlob(blob, `cover_letter_v${version}.docx`);
    } catch (err) {
      toast.error(`Download failed: ${(err as Error).message}`);
    }
  };

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
        <button
          type="button"
          onClick={downloadPdf}
          className={cn(
            "flex items-center justify-between gap-2 rounded px-2 py-1.5 w-full",
            "text-xs text-slate-700 hover:bg-slate-100 text-left",
            "focus:outline-none focus:bg-slate-100",
          )}
        >
          <span className="inline-flex items-center gap-2">
            <FileText className="h-3.5 w-3.5 text-slate-500" />
            PDF
          </span>
          <span className="text-[10px] text-slate-500">Universal</span>
        </button>
        <DownloadOption
          onClick={downloadDocx}
          label="Word (.docx)"
          hint="Best for ATS"
        />
      </PopoverContent>
    </Popover>
  );
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Release the object URL on the next tick so the browser has time to
  // start the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function DownloadOption({
  onClick,
  label,
  hint,
}: {
  onClick: () => void;
  label: string;
  hint: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center justify-between gap-2 rounded px-2 py-1.5 w-full",
        "text-xs text-slate-700 hover:bg-slate-100 text-left",
        "focus:outline-none focus:bg-slate-100",
      )}
    >
      <span className="inline-flex items-center gap-2">
        <FileText className="h-3.5 w-3.5 text-slate-500" />
        {label}
      </span>
      <span className="text-[10px] text-slate-500">{hint}</span>
    </button>
  );
}
