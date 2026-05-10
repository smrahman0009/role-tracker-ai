/**
 * LoginPage — two paths:
 *
 *   - "Try Demo": no token, public, fictional data, all backend
 *     calls intercepted client-side. For recruiters / the curious.
 *
 *   - "Sign in": existing private-beta flow — paste user_id + bearer
 *     token, hits the real backend.
 *
 * After either action, redirects to wherever the user was trying to
 * go before being bounced here, falling back to "/".
 */

import { Sparkles } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Input, Label } from "@/components/ui/Input";
import { useHealth } from "@/hooks/useHealth";
import { DEMO_USER_ID, enterDemoMode, exitDemoMode } from "@/lib/demoMode";

interface LocationState {
  from?: string;
}

export default function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as LocationState | undefined)?.from ?? "/";

  const [userId, setUserId] = useState("smrah");
  const [appToken, setAppToken] = useState("");

  // Pings /health on mount so the user knows whether the backend is reachable
  // before they bother to sign in. No auth required for /health.
  const health = useHealth();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId.trim()) return;
    // Clear any leftover demo flag from a prior session — otherwise
    // the api.ts interceptor keeps short-circuiting requests with
    // canned data instead of hitting the backend with the real token.
    exitDemoMode();
    signIn(userId.trim(), appToken.trim());
    navigate(from, { replace: true });
  };

  const handleTryDemo = () => {
    enterDemoMode();
    // Auth context still wants a user_id + token so the rest of the
    // app's URL building works. Use the synthetic demo user_id and
    // a placeholder token; the api.ts interceptor short-circuits
    // every request before either is sent over the wire.
    signIn(DEMO_USER_ID, "demo-token");
    navigate("/", { replace: true });
  };

  return (
    <main className="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md">
        <CardHeader className="border-b-0 pb-2">
          <div className="space-y-1.5">
            <CardTitle className="text-lg">Role Tracker</CardTitle>
            <CardDescription>
              Job-search assistant: ranked listings + AI-tailored cover
              letters.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* ---- Try Demo (primary CTA for visitors) ---- */}
          <div className="rounded-lg border border-indigo-200 bg-indigo-50/60 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-indigo-600" />
              <p className="text-sm font-medium text-indigo-900">
                New here?
              </p>
            </div>
            <p className="text-xs text-indigo-900/80">
              Explore with sample data — no sign-up required. Actions
              return pre-built results; nothing is saved or sent to AI.
            </p>
            <Button
              type="button"
              variant="primary"
              className="w-full"
              onClick={handleTryDemo}
            >
              Try the demo
            </Button>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-400">
            <div className="h-px flex-1 bg-slate-200" />
            <span>or sign in</span>
            <div className="h-px flex-1 bg-slate-200" />
          </div>

          {/* ---- Sign-in form (private beta) ---- */}
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-1.5">
              <Label htmlFor="user_id">User ID</Label>
              <Input
                id="user_id"
                autoComplete="username"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="smrah"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="app_token">
                API token{" "}
                <span className="font-normal text-slate-400">
                  (private beta)
                </span>
              </Label>
              <Input
                id="app_token"
                type="password"
                autoComplete="current-password"
                value={appToken}
                onChange={(e) => setAppToken(e.target.value)}
                placeholder="paste your token"
              />
            </div>
            <Button type="submit" variant="secondary" className="w-full">
              Sign in
            </Button>
            <p className="text-xs text-slate-500 text-center pt-1">
              Private beta. Your token is bound to one user_id;
              cross-user access is rejected by the backend.
            </p>
            <BackendStatus
              isLoading={health.isLoading}
              isError={health.isError}
              version={health.data?.version}
            />
          </form>
        </CardContent>
      </Card>
    </main>
  );
}


function BackendStatus({
  isLoading,
  isError,
  version,
}: {
  isLoading: boolean;
  isError: boolean;
  version: string | undefined;
}) {
  if (isLoading) {
    return (
      <p className="text-xs text-slate-400 text-center">
        Checking backend…
      </p>
    );
  }
  if (isError) {
    return (
      <p className="text-xs text-rose-600 text-center">
        Backend unreachable.
      </p>
    );
  }
  return (
    <p className="text-xs text-emerald-600 text-center">
      Backend reachable {version && <span className="text-slate-400">· v{version}</span>}
    </p>
  );
}
