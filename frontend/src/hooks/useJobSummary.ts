/**
 * useJobSummary — Phase 2.5. Plain-English 5-6 sentence summary of
 * the JD, on demand. Independent of the resume, so distinct from the
 * match analysis.
 *
 * Cached in the TanStack Query store keyed by (userId, jobId, model)
 * so flipping between Haiku and Sonnet for comparison purposes
 * doesn't fetch the previous one again.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type {
  CoverLetterSummaryRequest,
  CoverLetterSummaryResponse,
  ModelChoice,
} from "@/lib/types";

export interface JobSummaryEntry {
  data: CoverLetterSummaryResponse;
  model: ModelChoice;
}

const queryKey = (userId: string, jobId: string, model: ModelChoice) => [
  "job-summary",
  userId,
  jobId,
  model,
];

export function useJobSummary(jobId: string | undefined) {
  const { userId } = useAuth();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (body: CoverLetterSummaryRequest) =>
      api.post<CoverLetterSummaryResponse>(
        `/users/${userId}/jobs/${jobId}/cover-letter/summary`,
        body,
      ),
    onSuccess: (data, vars) => {
      const model = vars.model ?? "sonnet";
      queryClient.setQueryData(
        queryKey(userId ?? "", jobId ?? "", model),
        data,
      );
    },
  });

  /** Read the most recent cached summary for a given model, if any. */
  const cachedFor = (model: ModelChoice) =>
    queryClient.getQueryData<CoverLetterSummaryResponse>(
      queryKey(userId ?? "", jobId ?? "", model),
    );

  return { mutation, cachedFor };
}
