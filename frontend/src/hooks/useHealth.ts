/**
 * useHealth — pings GET /health. Used by LoginPage to validate that
 * the backend is reachable + the bearer token works before the user
 * commits to a session.
 *
 * No auth required for /health (per the spec), but if the user's
 * pasted token is invalid the rest of the app will 401 on first call.
 * To detect that early, we do a follow-up call to a protected
 * endpoint after sign-in — handled by the page, not here.
 */

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: () => api.get<HealthResponse>("/health"),
  });
}
