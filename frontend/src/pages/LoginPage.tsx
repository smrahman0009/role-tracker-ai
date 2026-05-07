/**
 * LoginPage — placeholder authentication that just stores user_id +
 * app_token in localStorage.
 *
 * Real OAuth/OIDC auth lands when the app goes multi-user (deferred to
 * a later phase per the locked plan). For now: paste your user_id and
 * the bearer token (or leave blank if backend's APP_TOKEN env var is
 * unset).
 *
 * After sign-in, redirects to wherever the user was trying to go before
 * being bounced here, falling back to "/".
 */

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
    signIn(userId.trim(), appToken.trim());
    navigate(from, { replace: true });
  };

  return (
    <main className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="border-b-0 pb-2">
          <div>
            <CardTitle className="text-base">Role Tracker</CardTitle>
            <CardDescription>Sign in to continue</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-1.5">
              <Label htmlFor="user_id">User ID</Label>
              <Input
                id="user_id"
                autoFocus
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
                  (optional in dev)
                </span>
              </Label>
              <Input
                id="app_token"
                type="password"
                autoComplete="current-password"
                value={appToken}
                onChange={(e) => setAppToken(e.target.value)}
                placeholder="leave blank if APP_TOKEN unset on backend"
              />
            </div>
            <Button type="submit" className="w-full">
              Sign in
            </Button>
            <p className="text-xs text-slate-500 text-center pt-1">
              Private beta. Your token is bound to one user_id; cross-user
              access is rejected by the backend.
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
        Backend unreachable. Is <code>scripts/run_api.py</code> running on
        port 8000?
      </p>
    );
  }
  return (
    <p className="text-xs text-emerald-600 text-center">
      Backend reachable {version && <span className="text-slate-400">· v{version}</span>}
    </p>
  );
}
