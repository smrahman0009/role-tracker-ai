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
import { api, ApiClientError } from "@/lib/api";
import type { ProfileResponse, UpdateProfileRequest } from "@/lib/types";

const EMPTY_PROFILE: ProfileResponse = {
  name: "",
  phone: "",
  email: "",
  city: "",
  linkedin_url: "",
  github_url: "",
  portfolio_url: "",
  show_phone_in_header: true,
  show_email_in_header: true,
  show_city_in_header: true,
  show_linkedin_in_header: true,
  show_github_in_header: true,
  show_portfolio_in_header: false,
};

export function useProfile() {
  const { userId } = useAuth();
  return useQuery<ProfileResponse>({
    queryKey: ["profile", userId],
    queryFn: async () => {
      try {
        return await api.get<ProfileResponse>(`/users/${userId}/profile`);
      } catch (err) {
        // No profile yet → render an empty form so the user can fill it in.
        if (err instanceof ApiClientError && err.status === 404) {
          return EMPTY_PROFILE;
        }
        throw err;
      }
    },
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
