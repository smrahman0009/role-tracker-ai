/**
 * useHiddenLists — GET + per-list PUT for the three Hidden filter
 * lists (companies, title keywords, publishers). Used by Settings.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api, ApiClientError } from "@/lib/api";
import type {
  HiddenListKind,
  HiddenListsResponse,
  UpdateHiddenListRequest,
} from "@/lib/types";

const EMPTY_HIDDEN: HiddenListsResponse = {
  companies: [],
  title_keywords: [],
  publishers: [],
};

export function useHiddenLists() {
  const { userId } = useAuth();
  return useQuery<HiddenListsResponse>({
    queryKey: ["hidden", userId],
    queryFn: async () => {
      try {
        return await api.get<HiddenListsResponse>(`/users/${userId}/hidden`);
      } catch (err) {
        // No profile yet → empty lists, so the user can add entries.
        if (err instanceof ApiClientError && err.status === 404) {
          return EMPTY_HIDDEN;
        }
        throw err;
      }
    },
    enabled: Boolean(userId),
  });
}

export function useUpdateHiddenList(kind: HiddenListKind) {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (items: string[]) =>
      api.put<string[]>(`/users/${userId}/hidden/${kind}`, {
        items,
      } satisfies UpdateHiddenListRequest),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hidden", userId] });
    },
  });
}
