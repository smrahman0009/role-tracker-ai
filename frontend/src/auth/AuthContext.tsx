/**
 * AuthContext — the app-wide source of truth for who's signed in.
 *
 * Exposes the current user_id + app_token plus signIn / signOut actions.
 * Backed by localStorage via lib/auth.ts so the session survives a
 * page refresh.
 *
 * Usage:
 *   const { userId, signOut } = useAuth();
 */

import * as React from "react";

import { clearAuth, getAuth, setAuth } from "@/lib/auth";

interface AuthContextValue {
  userId: string | null;
  appToken: string | null;
  signIn: (userId: string, appToken: string) => void;
  signOut: () => void;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuthState] = React.useState(() => getAuth());

  const signIn = React.useCallback((userId: string, appToken: string) => {
    setAuth(userId, appToken);
    setAuthState({ userId, appToken });
  }, []);

  const signOut = React.useCallback(() => {
    clearAuth();
    setAuthState({ userId: null, appToken: null });
  }, []);

  const value = React.useMemo<AuthContextValue>(
    () => ({
      userId: auth.userId,
      appToken: auth.appToken,
      signIn,
      signOut,
    }),
    [auth.userId, auth.appToken, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
