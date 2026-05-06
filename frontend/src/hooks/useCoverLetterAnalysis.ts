/**
 * useCoverLetterAnalysis — Phase 1 of the interactive cover-letter
 * flow. Triggers POST /cover-letter/analysis on demand (the call is
 * not free, so don't auto-fire on page mount).
 *
 * The result is cached in TanStack Query under
 * ["cover-letter-analysis", userId, jobId] so re-clicking "Run
 * analysis" within the same session is free; opening another job
 * recomputes.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type { CoverLetterAnalysisResponse } from "@/lib/types";

const queryKey = (userId: string, jobId: string) => [
  "cover-letter-analysis",
  userId,
  jobId,
];

export function useCoverLetterAnalysis(jobId: string | undefined) {
  const { userId } = useAuth();
  return useQuery<CoverLetterAnalysisResponse>({
    queryKey: queryKey(userId ?? "", jobId ?? ""),
    queryFn: () =>
      api.post<CoverLetterAnalysisResponse>(
        `/users/${userId}/jobs/${jobId}/cover-letter/analysis`,
      ),
    enabled: false, // user-triggered; see useRunCoverLetterAnalysis
    staleTime: Infinity, // cache for the session; re-running explicitly invalidates
  });
}

export function useRunCoverLetterAnalysis(jobId: string | undefined) {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post<CoverLetterAnalysisResponse>(
        `/users/${userId}/jobs/${jobId}/cover-letter/analysis`,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKey(userId ?? "", jobId ?? ""), data);
    },
  });
}
