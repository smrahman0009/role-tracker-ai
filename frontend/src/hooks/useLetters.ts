/**
 * Cover-letter hooks: list versions, fetch one, kick off generate /
 * regenerate / refine, poll generation status, manual-edit, and a
 * helper for the download URL.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type {
  GenerateLetterResponse,
  Letter,
  LetterGenerationStatus,
  LetterVersionList,
  ManualEditRequest,
  RefineLetterRequest,
} from "@/lib/types";

export function useLetterVersions(jobId: string | undefined) {
  const { userId } = useAuth();
  return useQuery<LetterVersionList>({
    queryKey: ["letters", userId, jobId],
    queryFn: () =>
      api.get<LetterVersionList>(`/users/${userId}/jobs/${jobId}/letters`),
    enabled: Boolean(userId && jobId),
  });
}

export function useGenerateLetter(jobId: string | undefined) {
  const { userId } = useAuth();
  return useMutation({
    mutationFn: () =>
      api.post<GenerateLetterResponse>(
        `/users/${userId}/jobs/${jobId}/letter/generate`,
      ),
  });
}

export function useRegenerateLetter(jobId: string | undefined) {
  const { userId } = useAuth();
  return useMutation({
    mutationFn: () =>
      api.post<GenerateLetterResponse>(
        `/users/${userId}/jobs/${jobId}/letter/regenerate`,
      ),
  });
}

export function useRefineLetter(
  jobId: string | undefined,
  version: number | undefined,
) {
  const { userId } = useAuth();
  return useMutation({
    mutationFn: (feedback: string) =>
      api.post<GenerateLetterResponse>(
        `/users/${userId}/jobs/${jobId}/letters/${version}/refine`,
        { feedback } satisfies RefineLetterRequest,
      ),
  });
}

export function useLetterGeneration(
  jobId: string | undefined,
  generationId: string | null,
) {
  const { userId } = useAuth();
  return useQuery<LetterGenerationStatus>({
    queryKey: ["letter-gen", userId, jobId, generationId],
    queryFn: () =>
      api.get<LetterGenerationStatus>(
        `/users/${userId}/jobs/${jobId}/letter/generations/${generationId}`,
      ),
    enabled: Boolean(userId && jobId && generationId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "failed" ? false : 2000;
    },
  });
}

export function useEditLetter(
  jobId: string | undefined,
  version: number | undefined,
) {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (text: string) =>
      api.post<Letter>(
        `/users/${userId}/jobs/${jobId}/letters/${version}/edit`,
        { text } satisfies ManualEditRequest,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["letters", userId, jobId],
      });
    },
  });
}

export function letterDownloadUrl(
  userId: string,
  jobId: string,
  version: number,
): string {
  return `/api/users/${userId}/jobs/${jobId}/letters/${version}/download`;
}
