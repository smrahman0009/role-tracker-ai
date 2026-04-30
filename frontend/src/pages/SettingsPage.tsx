/**
 * SettingsPage — resume, profile (with per-field show-in-letter toggles),
 * daily auto-search, and the three Hidden lists. Each section owns its
 * own loading/error/save state; the page just lays them out.
 */

import {
  AlertCircle,
  CheckCircle2,
  FileUp,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { TagListEditor } from "@/components/TagListEditor";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import { Input, Label } from "@/components/ui/Input";
import { toast } from "@/components/ui/Toaster";
import { formatBytes, formatDateTime } from "@/lib/format";
import { useHiddenLists, useUpdateHiddenList } from "@/hooks/useHiddenLists";
import { useProfile, useUpdateProfile } from "@/hooks/useProfile";
import {
  useCreateQuery,
  useDeleteQuery,
  useSavedQueries,
  useUpdateQuery,
} from "@/hooks/useQueries";
import { useResume, useUploadResume } from "@/hooks/useResume";
import type {
  HiddenListKind,
  ProfileResponse,
  SavedQuery,
} from "@/lib/types";

export default function SettingsPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
          Settings
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Resume, contact info, daily auto-search, and hidden lists.
        </p>
      </div>

      <div className="space-y-5">
        <ResumeSection />
        <ProfileSection />
        <SavedSearchesSection />
        <HiddenListsSection />
      </div>
    </div>
  );
}

// ---------- Resume ----------

function ResumeSection() {
  const resumeQuery = useResume();
  const upload = useUploadResume();
  const fileRef = useRef<HTMLInputElement>(null);

  const handlePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    upload.mutate(file, {
      onSuccess: () => toast.success("Resume uploaded"),
      onError: (err) => toast.error(`Upload failed: ${err.message}`),
    });
    e.target.value = ""; // allow re-selecting the same file
  };

  const meta = resumeQuery.data;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Resume</CardTitle>
          <CardDescription>
            PDF only. We extract text once on upload and reuse it on every
            generation.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {resumeQuery.isLoading ? (
          <p className="text-xs text-slate-500">Loading…</p>
        ) : meta ? (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-900 truncate">
                {meta.filename}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                {formatBytes(meta.size_bytes)} · uploaded{" "}
                {formatDateTime(meta.uploaded_at)}
              </p>
            </div>
            <Button
              variant="secondary"
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
          <div className="rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center">
            <FileUp className="h-5 w-5 text-slate-400 mx-auto" />
            <p className="text-sm text-slate-700 mt-2">No resume uploaded</p>
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

// ---------- Profile ----------

const PROFILE_FIELDS: Array<{
  key: keyof ProfileResponse;
  toggleKey?: keyof ProfileResponse;
  label: string;
  type?: string;
  placeholder?: string;
}> = [
  { key: "name", label: "Name", placeholder: "Jane Doe" },
  {
    key: "phone",
    toggleKey: "show_phone_in_header",
    label: "Phone",
    type: "tel",
    placeholder: "+1 (555) 123-4567",
  },
  {
    key: "email",
    toggleKey: "show_email_in_header",
    label: "Email",
    type: "email",
    placeholder: "jane@example.com",
  },
  {
    key: "city",
    toggleKey: "show_city_in_header",
    label: "City",
    placeholder: "Toronto, Canada",
  },
  {
    key: "linkedin_url",
    toggleKey: "show_linkedin_in_header",
    label: "LinkedIn",
    type: "url",
    placeholder: "https://linkedin.com/in/…",
  },
  {
    key: "github_url",
    toggleKey: "show_github_in_header",
    label: "GitHub",
    type: "url",
    placeholder: "https://github.com/…",
  },
  {
    key: "portfolio_url",
    toggleKey: "show_portfolio_in_header",
    label: "Portfolio",
    type: "url",
    placeholder: "https://…",
  },
];

function ProfileSection() {
  const profileQuery = useProfile();
  const updateProfile = useUpdateProfile();
  const [draft, setDraft] = useState<ProfileResponse | null>(null);

  useEffect(() => {
    if (profileQuery.data) setDraft(profileQuery.data);
  }, [profileQuery.data]);

  const dirty =
    draft && profileQuery.data
      ? JSON.stringify(draft) !== JSON.stringify(profileQuery.data)
      : false;

  const save = () => {
    if (!draft) return;
    updateProfile.mutate(draft, {
      onSuccess: () => toast.success("Profile saved"),
      onError: (err) => toast.error(`Save failed: ${err.message}`),
    });
  };

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Contact info</CardTitle>
          <CardDescription>
            Stored once; the agent uses these in the letter header. Toggle
            "show in letter" off to keep a value on file but not include
            it in the rendered header.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {profileQuery.isLoading || !draft ? (
          <p className="text-xs text-slate-500">Loading…</p>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-4">
              {PROFILE_FIELDS.map((f) => (
                <div key={f.key}>
                  <div className="flex items-center justify-between gap-2">
                    <Label htmlFor={String(f.key)}>{f.label}</Label>
                    {f.toggleKey && (
                      <label className="inline-flex items-center gap-1.5 text-[11px] text-slate-500 cursor-pointer">
                        <Checkbox
                          checked={Boolean(draft[f.toggleKey])}
                          onCheckedChange={(c) =>
                            setDraft({
                              ...draft,
                              [f.toggleKey!]: c === true,
                            })
                          }
                        />
                        Show in letter
                      </label>
                    )}
                  </div>
                  <Input
                    id={String(f.key)}
                    type={f.type ?? "text"}
                    placeholder={f.placeholder}
                    value={(draft[f.key] as string) ?? ""}
                    onChange={(e) =>
                      setDraft({ ...draft, [f.key]: e.target.value })
                    }
                    className="mt-1"
                  />
                </div>
              ))}
            </div>

            <div className="mt-5 pt-5 border-t border-slate-100">
              <div className="flex items-baseline justify-between gap-3">
                <Label htmlFor="top_n_jobs">Max jobs to keep per refresh</Label>
                <span className="text-[11px] text-slate-500 tabular-nums">
                  {draft.top_n_jobs}
                </span>
              </div>
              <Input
                id="top_n_jobs"
                type="number"
                min={1}
                max={200}
                step={5}
                value={draft.top_n_jobs}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  if (Number.isFinite(n)) {
                    setDraft({
                      ...draft,
                      top_n_jobs: Math.max(1, Math.min(200, Math.round(n))),
                    });
                  }
                }}
                className="mt-1 max-w-[140px]"
              />
              <p className="text-[11px] text-slate-500 mt-1.5">
                After fetching, jobs are ranked by similarity to your resume
                and the top N are kept. Higher = more browsing freedom; lower
                = only the best matches. Range 1–200.
              </p>
            </div>

            <div className="flex justify-end mt-5 gap-2">
              <Button
                variant="ghost"
                onClick={() => setDraft(profileQuery.data ?? null)}
                disabled={!dirty || updateProfile.isPending}
              >
                Reset
              </Button>
              <Button
                onClick={save}
                disabled={!dirty || updateProfile.isPending}
              >
                {updateProfile.isPending ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ---------- Daily auto-search ----------

function SavedSearchesSection() {
  const queriesQuery = useSavedQueries();
  const createQuery = useCreateQuery();
  const updateQuery = useUpdateQuery();
  const deleteQuery = useDeleteQuery();

  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const queries = queriesQuery.data?.queries ?? [];

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Daily auto-search</CardTitle>
          <CardDescription>
            Searches that will run automatically once a day, in addition
            to anything you search ad-hoc on the home page. Disable a row
            to keep it on file without running it. (The scheduler ships
            with deployment — for now these are dormant.)
          </CardDescription>
        </div>
        {!adding && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setAdding(true)}
          >
            <Plus />
            New search
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {queriesQuery.isLoading ? (
          <p className="text-xs text-slate-500">Loading…</p>
        ) : queries.length === 0 && !adding ? (
          <p className="text-xs text-slate-500">
            No daily searches yet. Add one to have it run automatically
            every day, or use the home-page search box for one-off queries.
          </p>
        ) : (
          <div className="space-y-2">
            {queries.map((q) =>
              editingId === q.query_id ? (
                <QueryRowEditor
                  key={q.query_id}
                  initial={q}
                  isSubmitting={updateQuery.isPending}
                  onCancel={() => setEditingId(null)}
                  onSubmit={(body) =>
                    updateQuery.mutate(
                      { id: q.query_id, body },
                      {
                        onSuccess: () => {
                          toast.success("Search updated");
                          setEditingId(null);
                        },
                        onError: (err) =>
                          toast.error(`Update failed: ${err.message}`),
                      },
                    )
                  }
                />
              ) : (
                <QueryRow
                  key={q.query_id}
                  query={q}
                  onToggle={(enabled) =>
                    updateQuery.mutate(
                      { id: q.query_id, body: { enabled } },
                      {
                        onError: (err) => toast.error(err.message),
                      },
                    )
                  }
                  onEdit={() => setEditingId(q.query_id)}
                  onDelete={() => {
                    if (!confirm(`Delete "${q.what} in ${q.where}"?`)) return;
                    deleteQuery.mutate(q.query_id, {
                      onSuccess: () => toast.success("Deleted"),
                      onError: (err) => toast.error(err.message),
                    });
                  }}
                />
              ),
            )}
          </div>
        )}

        {adding && (
          <div className="mt-3">
            <QueryRowEditor
              initial={null}
              isSubmitting={createQuery.isPending}
              onCancel={() => setAdding(false)}
              onSubmit={(body) =>
                createQuery.mutate(
                  { what: body.what ?? "", where: body.where ?? "" },
                  {
                    onSuccess: () => {
                      toast.success("Search added");
                      setAdding(false);
                    },
                    onError: (err) =>
                      toast.error(`Add failed: ${err.message}`),
                  },
                )
              }
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function QueryRow({
  query,
  onToggle,
  onEdit,
  onDelete,
}: {
  query: SavedQuery;
  onToggle: (enabled: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 px-4 py-3">
      <label className="inline-flex items-center gap-2 cursor-pointer">
        <Checkbox
          checked={query.enabled}
          onCheckedChange={(c) => onToggle(c === true)}
        />
      </label>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-900 truncate">
          <span className="font-medium">{query.what}</span>
          <span className="text-slate-400 mx-1.5">in</span>
          {query.where}
        </p>
        {!query.enabled && (
          <p className="text-[11px] text-slate-500 mt-0.5">Disabled</p>
        )}
      </div>
      <Button variant="ghost" size="sm" onClick={onEdit} aria-label="Edit">
        <Pencil />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onDelete}
        aria-label="Delete"
      >
        <Trash2 />
      </Button>
    </div>
  );
}

function QueryRowEditor({
  initial,
  isSubmitting,
  onCancel,
  onSubmit,
}: {
  initial: SavedQuery | null;
  isSubmitting: boolean;
  onCancel: () => void;
  onSubmit: (body: { what?: string; where?: string }) => void;
}) {
  const [what, setWhat] = useState(initial?.what ?? "");
  const [where, setWhere] = useState(initial?.where ?? "");

  const submit = () => {
    const w = what.trim();
    const wh = where.trim();
    if (!w || !wh) {
      toast.error("Both 'what' and 'where' are required");
      return;
    }
    onSubmit({ what: w, where: wh });
  };

  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50/40 px-4 py-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <Label htmlFor="what">What</Label>
          <Input
            id="what"
            placeholder="e.g. data scientist"
            value={what}
            onChange={(e) => setWhat(e.target.value)}
            autoFocus
            className="mt-1"
          />
        </div>
        <div>
          <Label htmlFor="where">Where</Label>
          <Input
            id="where"
            placeholder="e.g. Toronto, Canada or Remote"
            value={where}
            onChange={(e) => setWhere(e.target.value)}
            className="mt-1"
          />
        </div>
      </div>
      <div className="flex justify-end gap-2 mt-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          <X />
          Cancel
        </Button>
        <Button size="sm" onClick={submit} disabled={isSubmitting}>
          <CheckCircle2 />
          {isSubmitting ? "Saving…" : initial ? "Update" : "Add"}
        </Button>
      </div>
    </div>
  );
}

// ---------- Hidden lists ----------

const HIDDEN_SECTIONS: Array<{
  kind: HiddenListKind;
  field: keyof import("@/lib/types").HiddenListsResponse;
  title: string;
  description: string;
  placeholder: string;
}> = [
  {
    kind: "companies",
    field: "companies",
    title: "Hidden companies",
    description:
      "Jobs posted by these companies are excluded from your results.",
    placeholder: "e.g. Acme Corp",
  },
  {
    kind: "title-keywords",
    field: "title_keywords",
    title: "Hidden title keywords",
    description:
      "Jobs whose title contains any of these substrings are excluded.",
    placeholder: "e.g. senior, lead",
  },
  {
    kind: "publishers",
    field: "publishers",
    title: "Hidden publishers",
    description:
      "Jobs from these listing sources are excluded.",
    placeholder: "e.g. some-board.com",
  },
];

function HiddenListsSection() {
  const hiddenQuery = useHiddenLists();
  const data = hiddenQuery.data;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Hidden lists</CardTitle>
          <CardDescription>
            Filtered out before ranking. Useful for cutting noise from the
            daily refresh.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {hiddenQuery.isLoading || !data ? (
          <p className="text-xs text-slate-500">Loading…</p>
        ) : (
          HIDDEN_SECTIONS.map((s) => (
            <HiddenListEditor
              key={s.kind}
              kind={s.kind}
              title={s.title}
              description={s.description}
              placeholder={s.placeholder}
              initial={data[s.field]}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}

function HiddenListEditor({
  kind,
  title,
  description,
  placeholder,
  initial,
}: {
  kind: HiddenListKind;
  title: string;
  description: string;
  placeholder: string;
  initial: string[];
}) {
  const updater = useUpdateHiddenList(kind);
  const [items, setItems] = useState<string[]>(initial);

  // Keep local state in sync if the cached query updates from elsewhere.
  useEffect(() => {
    setItems(initial);
  }, [initial]);

  const dirty = JSON.stringify(items) !== JSON.stringify(initial);

  const save = () => {
    updater.mutate(items, {
      onSuccess: () => toast.success(`${title} saved`),
      onError: (err) => toast.error(`Save failed: ${err.message}`),
    });
  };

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <h3 className="text-sm font-medium text-slate-900">{title}</h3>
          <p className="text-xs text-slate-500 mt-0.5">{description}</p>
        </div>
        {items.length > 0 && (
          <button
            type="button"
            onClick={() => setItems([])}
            className="text-xs text-slate-500 hover:text-slate-900 underline underline-offset-2"
          >
            Clear all
          </button>
        )}
      </div>
      <TagListEditor
        items={items}
        onChange={setItems}
        placeholder={placeholder}
      />
      <div className="flex justify-end mt-2 gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setItems(initial)}
          disabled={!dirty || updater.isPending}
        >
          Reset
        </Button>
        <Button
          size="sm"
          onClick={save}
          disabled={!dirty || updater.isPending}
        >
          {updater.isPending ? "Saving…" : "Save"}
        </Button>
      </div>
      {updater.isError && (
        <p className="mt-1 text-xs text-rose-700 inline-flex items-center gap-1">
          <AlertCircle className="h-3 w-3" />
          {updater.error.message}
        </p>
      )}
    </div>
  );
}

