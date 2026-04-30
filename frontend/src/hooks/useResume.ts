/**
 * Resume metadata + upload hook. The backend stores a single resume
 * per user; uploading replaces the existing one.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api, ApiClientError } from "@/lib/api";
import type { ResumeMetadata, ResumeUploadResponse } from "@/lib/types";

export function useResume() {
  const { userId } = useAuth();
  return useQuery<ResumeMetadata | null>({
    queryKey: ["resume", userId],
    queryFn: async () => {
      try {
        return await api.get<ResumeMetadata>(`/users/${userId}/resume`);
      } catch (err) {
        // 404 means no resume uploaded yet — that's a valid empty state.
        if (err instanceof ApiClientError && err.status === 404) return null;
        throw err;
      }
    },
    enabled: Boolean(userId),
  });
}

export function useUploadResume() {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.upload<ResumeUploadResponse>(`/users/${userId}/resume`, fd);
    },
    onSuccess: (data) => {
      // Cache the metadata under the resume key, sans prefilled_fields.
      const { prefilled_fields: _ignored, ...meta } = data;
      queryClient.setQueryData(["resume", userId], meta as ResumeMetadata);
      // Profile may have been auto-filled — invalidate so Settings shows
      // the new values next time it renders.
      if (data.prefilled_fields.length > 0) {
        queryClient.invalidateQueries({ queryKey: ["profile", userId] });
      }
    },
  });
}
