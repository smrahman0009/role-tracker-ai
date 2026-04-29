/**
 * Saved-search CRUD hooks. Each user has up to N saved searches; the
 * daily refresh fans out across all enabled ones.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type {
  CreateQueryRequest,
  QueryListResponse,
  SavedQuery,
  UpdateQueryRequest,
} from "@/lib/types";

export function useSavedQueries() {
  const { userId } = useAuth();
  return useQuery<QueryListResponse>({
    queryKey: ["queries", userId],
    queryFn: () => api.get<QueryListResponse>(`/users/${userId}/queries`),
    enabled: Boolean(userId),
  });
}

export function useCreateQuery() {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateQueryRequest) =>
      api.post<SavedQuery>(`/users/${userId}/queries`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queries", userId] });
    },
  });
}

export function useUpdateQuery() {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateQueryRequest }) =>
      api.put<SavedQuery>(`/users/${userId}/queries/${id}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queries", userId] });
    },
  });
}

export function useDeleteQuery() {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.del<void>(`/users/${userId}/queries/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queries", userId] });
    },
  });
}
