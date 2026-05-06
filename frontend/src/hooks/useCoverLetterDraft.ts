/**
 * useCoverLetterDraft — Phase 2 of the interactive cover-letter flow.
 * One paragraph at a time, plus a finalize step that saves the
 * assembled letter as a new version.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type {
  CoverLetterDraftRequest,
  CoverLetterDraftResponse,
  CoverLetterFinalizeRequest,
  Letter,
} from "@/lib/types";

export function useCoverLetterDraft(jobId: string | undefined) {
  const { userId } = useAuth();
  return useMutation({
    mutationFn: (body: CoverLetterDraftRequest) =>
      api.post<CoverLetterDraftResponse>(
        `/users/${userId}/jobs/${jobId}/cover-letter/draft`,
        body,
      ),
  });
}

export function useCoverLetterFinalize(jobId: string | undefined) {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CoverLetterFinalizeRequest) =>
      api.post<Letter>(
        `/users/${userId}/jobs/${jobId}/cover-letter/finalize`,
        body,
      ),
    onSuccess: () => {
      // The new letter is a real version; the existing letters list
      // should refetch so it shows up in the workspace.
      queryClient.invalidateQueries({
        queryKey: ["letters", userId, jobId],
      });
    },
  });
}
