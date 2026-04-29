/**
 * RequireAuth — gate component for protected routes.
 *
 * If the user isn't signed in, redirects to /login while preserving the
 * destination they were trying to reach (via the `from` location state).
 * After signing in, LoginPage reads that state and routes them back.
 *
 * Wraps the whole authenticated section of the route tree:
 *
 *   <Route element={<RequireAuth><Layout /></RequireAuth>}>
 *     <Route path="/" element={<JobListPage />} />
 *     ...
 *   </Route>
 */

import { Navigate, useLocation } from "react-router";

import { useAuth } from "@/auth/AuthContext";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { userId } = useAuth();
  const location = useLocation();

  if (!userId) {
    return (
      <Navigate to="/login" state={{ from: location.pathname }} replace />
    );
  }

  return <>{children}</>;
}
