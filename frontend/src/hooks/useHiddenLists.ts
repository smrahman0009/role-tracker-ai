/**
 * useHiddenLists — GET + per-list PUT for the three Hidden filter
 * lists (companies, title keywords, publishers). Used by Settings.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type {
  HiddenListKind,
  HiddenListsResponse,
  UpdateHiddenListRequest,
} from "@/lib/types";

export function useHiddenLists() {
  const { userId } = useAuth();
  return useQuery<HiddenListsResponse>({
    queryKey: ["hidden", userId],
    queryFn: () => api.get<HiddenListsResponse>(`/users/${userId}/hidden`),
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
