/**
 * SettingsPage — placeholder. Full implementation in a later commit.
 *
 * Final design lives in docs/wireframes/settings_mockup.html — covers
 * resume, contact info with per-field show-in-letter toggles, saved
 * searches, and the three Hidden lists.
 */

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";

export default function SettingsPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
          Settings
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Placeholder. Real form lands when API client + TanStack Query
          hooks are in place.
        </p>
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Coming soon</CardTitle>
            <CardDescription>
              Resume upload, contact info, saved searches, hidden lists.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="text-sm text-slate-600">
          Reference: <code className="mx-1 px-1 py-0.5 bg-slate-100 rounded text-xs">docs/wireframes/settings_mockup.html</code>
        </CardContent>
      </Card>
    </div>
  );
}
