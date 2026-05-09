/**
 * useCoverLetterAnalysis — match analysis (Strong / Gaps / Partial /
 * Excitement) on the resume vs the JD.
 *
 * The call is not free (~$0.02 with Sonnet, ~$0.005 with Haiku), so
 * it doesn't auto-fire on page mount. The user clicks "Run analysis";
 * the result is cached in TanStack Query for the session.
 *
 * Sonnet is the default; the panel exposes a model toggle so the
 * user can downgrade to Haiku for a cheaper run.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type {
  CoverLetterAnalysisRequest,
  CoverLetterAnalysisResponse,
} from "@/lib/types";

const queryKey = (userId: string, jobId: string) => [
  "cover-letter-analysis",
  userId,
  jobId,
];

export function useCoverLetterAnalysis(jobId: string | undefined) {
  const { userId } = useAuth();
  return useQuery<CoverLetterAnalysisResponse>({
    queryKey: queryKey(userId ?? "", jobId ?? ""),
    // user-triggered (see useRunCoverLetterAnalysis below); this query
    // exists only to read the cached value when one's there.
    queryFn: () => Promise.reject(new Error("disabled")),
    enabled: false,
    staleTime: Infinity,
  });
}

export function useRunCoverLetterAnalysis(jobId: string | undefined) {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CoverLetterAnalysisRequest) =>
      api.post<CoverLetterAnalysisResponse>(
        `/users/${userId}/jobs/${jobId}/cover-letter/analysis`,
        body,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKey(userId ?? "", jobId ?? ""), data);
    },
  });
}
