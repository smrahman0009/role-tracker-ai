/**
 * ResumeCard — compact card for the home page. Shows current resume
 * metadata if uploaded, or an "Upload your resume" tile if not. Calls
 * onResumeChange after a successful upload so the parent can re-enable
 * its search button.
 */

import { FileText, FileUp, Loader2 } from "lucide-react";
import { useRef } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { toast } from "@/components/ui/Toaster";
import { useResume, useUploadResume } from "@/hooks/useResume";
import { formatBytes, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ResumeCard({
  onResumeChange,
}: {
  onResumeChange?: () => void;
}) {
  const resumeQuery = useResume();
  const upload = useUploadResume();
  const fileRef = useRef<HTMLInputElement>(null);

  const handlePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    upload.mutate(file, {
      onSuccess: () => {
        toast.success("Resume uploaded");
        onResumeChange?.();
      },
      onError: (err) => toast.error(`Upload failed: ${err.message}`),
    });
    e.target.value = "";
  };

  const meta = resumeQuery.data;

  return (
    <Card>
      <CardContent
        className={cn(
          "py-4 px-5",
          !meta && !resumeQuery.isLoading && "py-6",
        )}
      >
        {resumeQuery.isLoading ? (
          <p className="text-xs text-slate-500">Loading resume…</p>
        ) : meta ? (
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-slate-500 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-900 truncate">
                {meta.filename}
              </p>
              <p className="text-[11px] text-slate-500">
                {formatBytes(meta.size_bytes)} · uploaded{" "}
                {formatDateTime(meta.uploaded_at)}
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => fileRef.current?.click()}
              disabled={upload.isPending}
            >
              {upload.isPending ? (
                <Loader2 className="animate-spin" />
              ) : (
                <FileUp />
              )}
              Replace
            </Button>
          </div>
        ) : (
          <div className="text-center">
            <FileUp className="h-5 w-5 text-slate-400 mx-auto" />
            <p className="text-sm text-slate-700 mt-2">
              Upload your resume to start
            </p>
            <p className="text-[11px] text-slate-500 mt-1 max-w-sm mx-auto">
              Job results are ranked by similarity to your resume. PDF only,
              up to 5 MB.
            </p>
            <Button
              size="sm"
              onClick={() => fileRef.current?.click()}
              disabled={upload.isPending}
              className="mt-3"
            >
              {upload.isPending ? (
                <Loader2 className="animate-spin" />
              ) : (
                <FileUp />
              )}
              Upload PDF
            </Button>
          </div>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={handlePick}
        />
      </CardContent>
    </Card>
  );
}
