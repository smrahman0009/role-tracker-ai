/**
 * useUsage — pulls the current month's external-API call counts +
 * cost estimates plus up to five prior months.
 *
 * Backed by GET /users/{user_id}/usage.
 */

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type { UsageResponse } from "@/lib/types";

export function useUsage() {
  const { userId } = useAuth();
  return useQuery<UsageResponse>({
    queryKey: ["usage", userId],
    queryFn: () => api.get<UsageResponse>(`/users/${userId}/usage`),
    enabled: Boolean(userId),
    // Usage moves slowly during a session; refetching when the user
    // switches tabs is enough.
    staleTime: 60_000,
  });
}
