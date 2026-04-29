/**
 * TagListEditor — controlled tag input. Used for hidden-list editors
 * on Settings (companies, title keywords, publishers). User types,
 * presses Enter or comma to commit; pills display with × to remove.
 *
 * The list is committed *locally* via onChange. The parent decides
 * when to PUT (typically a "Save" button so users can stage edits).
 */

import { Plus, X } from "lucide-react";
import { useState } from "react";

import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/utils";

interface TagListEditorProps {
  items: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  caseInsensitiveDedupe?: boolean;
}

export function TagListEditor({
  items,
  onChange,
  placeholder,
  caseInsensitiveDedupe = true,
}: TagListEditorProps) {
  const [draft, setDraft] = useState("");

  const commit = () => {
    const v = draft.trim();
    if (!v) return;
    const exists = caseInsensitiveDedupe
      ? items.some((it) => it.toLowerCase() === v.toLowerCase())
      : items.includes(v);
    if (!exists) onChange([...items, v]);
    setDraft("");
  };

  return (
    <div>
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              commit();
            } else if (e.key === "Backspace" && !draft && items.length) {
              onChange(items.slice(0, -1));
            }
          }}
          onBlur={commit}
          placeholder={placeholder}
        />
        <button
          type="button"
          onClick={commit}
          disabled={!draft.trim()}
          className={cn(
            "shrink-0 inline-flex items-center gap-1 rounded-lg border px-3 py-2 text-xs font-medium",
            "border-slate-200 text-slate-700 hover:bg-slate-50",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          <Plus className="h-3 w-3" />
          Add
        </button>
      </div>
      {items.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {items.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-800"
            >
              {tag}
              <button
                type="button"
                onClick={() => onChange(items.filter((it) => it !== tag))}
                className="text-slate-500 hover:text-slate-900"
                aria-label={`Remove ${tag}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-xs text-slate-400">No items yet.</p>
      )}
    </div>
  );
}
