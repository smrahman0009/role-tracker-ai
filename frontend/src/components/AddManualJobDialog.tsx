/**
 * AddManualJobDialog — paste a URL or copy-paste a JD into a textarea
 * to add a job that didn't come from JSearch (referrals, direct career
 * pages, smaller boards). Once saved, the job lives in seen_jobs with
 * source="manual" and every existing flow works (cover letter, refine,
 * polish, Apply Kit, Mark applied → My Applications).
 *
 * Flow:
 *   1. (Optional) paste URL → click Fetch → backend tries Trafilatura
 *   2. If extraction succeeded, title/company/JD pre-fill
 *   3. Otherwise the user pastes the JD into the textarea themselves
 *   4. Title and Company are required (sometimes auto-filled too)
 *   5. Submit → job created, navigate to its detail page
 */

import { Loader2, Plus, Wand } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input, Label, Textarea } from "@/components/ui/Input";
import { toast } from "@/components/ui/Toaster";
import { useCreateManualJob, useFetchJobUrl } from "@/hooks/useJobs";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddManualJobDialog({ open, onOpenChange }: Props) {
  const navigate = useNavigate();
  const fetchUrl = useFetchJobUrl();
  const createJob = useCreateManualJob();

  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");

  const reset = () => {
    setUrl("");
    setTitle("");
    setCompany("");
    setLocation("");
    setDescription("");
  };

  const fetchFromUrl = () => {
    const v = url.trim();
    if (!v) return;
    fetchUrl.mutate(v, {
      onSuccess: (data) => {
        // Only overwrite empty fields — don't stomp on edits the user
        // already made.
        if (data.title && !title.trim()) setTitle(data.title);
        if (data.company && !company.trim()) setCompany(data.company);
        if (data.location && !location.trim()) setLocation(data.location);
        if (data.description && !description.trim()) {
          setDescription(data.description);
        }
        if (!data.description) {
          toast(
            "Couldn't extract from this URL — paste the description below instead.",
            { duration: 6000 },
          );
        } else {
          toast.success(
            "Pulled the listing — review the fields and edit as needed.",
          );
        }
      },
      onError: (err) =>
        toast.error(`Fetch failed: ${err.message}`),
    });
  };

  const ready =
    !createJob.isPending &&
    title.trim().length > 0 &&
    company.trim().length > 0 &&
    description.trim().length >= 50;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready) return;
    createJob.mutate(
      {
        title: title.trim(),
        company: company.trim(),
        description: description.trim(),
        location: location.trim() || undefined,
        url: url.trim() || undefined,
      },
      {
        onSuccess: (job) => {
          toast.success("Job added");
          reset();
          onOpenChange(false);
          navigate(`/jobs/${encodeURIComponent(job.job_id)}`);
        },
        onError: (err) =>
          toast.error(`Couldn't add job: ${err.message}`),
      },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="h-4 w-4 text-indigo-600" />
            Add a job manually
          </DialogTitle>
          <DialogDescription>
            For postings JSearch didn't find — referrals, smaller boards,
            direct career pages. Paste a URL and we'll try to extract the
            description, or paste it yourself in the textarea.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="manual-url">URL</Label>
            <div className="flex gap-2 mt-1">
              <Input
                id="manual-url"
                type="url"
                placeholder="https://acme.com/careers/12345"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={createJob.isPending}
              />
              <Button
                type="button"
                variant="secondary"
                onClick={fetchFromUrl}
                disabled={
                  fetchUrl.isPending ||
                  createJob.isPending ||
                  !url.trim()
                }
                title="Try to extract title / company / description from this URL"
              >
                {fetchUrl.isPending ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <Wand />
                )}
                Fetch
              </Button>
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Works on most static career pages (Greenhouse, Lever, etc).
              Workday and LinkedIn won't extract — paste manually below.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="manual-title">Title *</Label>
              <Input
                id="manual-title"
                placeholder="Senior ML Engineer"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={createJob.isPending}
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="manual-company">Company *</Label>
              <Input
                id="manual-company"
                placeholder="Acme Corp"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                disabled={createJob.isPending}
                className="mt-1"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="manual-location">Location</Label>
            <Input
              id="manual-location"
              placeholder="Halifax, Canada"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              disabled={createJob.isPending}
              className="mt-1"
            />
          </div>

          <div>
            <Label htmlFor="manual-jd">Job description *</Label>
            <Textarea
              id="manual-jd"
              rows={10}
              placeholder="Paste the full job description here. The agent uses this to write your cover letter."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={createJob.isPending}
              className="mt-1 text-sm"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              {description.length} chars
              {description.length < 50 && (
                <span className="text-rose-600">
                  {" "}
                  · need at least 50 to save
                </span>
              )}
            </p>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              onClick={() => onOpenChange(false)}
              disabled={createJob.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!ready}>
              {createJob.isPending ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Plus />
              )}
              {createJob.isPending ? "Adding…" : "Add job"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
