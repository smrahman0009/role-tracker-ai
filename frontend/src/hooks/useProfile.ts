/**
 * useProfile — GET + PUT for the user's profile (contact info +
 * per-field show-in-letter flags). Used by the Settings page.
 *
 * Demonstrates the standard query+mutation pattern for the app:
 *  - useQuery returns {data, isLoading, error}
 *  - useMutation returns {mutate, isPending, error} + success/error callbacks
 *  - On mutation success we invalidate the matching query so the UI
 *    re-fetches automatically without an explicit refresh.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type { ProfileResponse, UpdateProfileRequest } from "@/lib/types";

export function useProfile() {
  const { userId } = useAuth();
  return useQuery<ProfileResponse>({
    queryKey: ["profile", userId],
    queryFn: () => api.get<ProfileResponse>(`/users/${userId}/profile`),
    enabled: Boolean(userId),
  });
}

export function useUpdateProfile() {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateProfileRequest) =>
      api.put<ProfileResponse>(`/users/${userId}/profile`, body),
    onSuccess: (data) => {
      queryClient.setQueryData(["profile", userId], data);
    },
  });
}
