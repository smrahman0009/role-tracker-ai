/**
 * Cover-letter hooks: list versions, fetch one, kick off generate /
 * regenerate / refine, poll generation status, manual-edit, and a
 * helper for the download URL.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type {
  GenerateLetterRequest,
  GenerateLetterResponse,
  Letter,
  LetterGenerationStatus,
  LetterVersionList,
  ManualEditRequest,
  PolishLetterRequest,
  PolishLetterResponse,
  PolishWhyInterestedRequest,
  RefineLetterRequest,
  WhyInterestedResponse,
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
    mutationFn: (body: GenerateLetterRequest = {}) =>
      api.post<GenerateLetterResponse>(
        `/users/${userId}/jobs/${jobId}/letters`,
        body,
      ),
  });
}

export function useRefineLetter(
  jobId: string | undefined,
  version: number | undefined,
) {
  const { userId } = useAuth();
  return useMutation({
    mutationFn: (body: RefineLetterRequest) =>
      api.post<GenerateLetterResponse>(
        `/users/${userId}/jobs/${jobId}/letters/${version}/refine`,
        body,
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
        `/users/${userId}/letter-jobs/${generationId}`,
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


export function usePolishLetter(
  jobId: string | undefined,
  version: number | undefined,
) {
  const { userId } = useAuth();
  return useMutation({
    mutationFn: (text: string) =>
      api.post<PolishLetterResponse>(
        `/users/${userId}/jobs/${jobId}/letters/${version}/polish`,
        { text } satisfies PolishLetterRequest,
      ),
  });
}

export function usePolishWhyInterested(jobId: string | undefined) {
  const { userId } = useAuth();
  return useMutation({
    mutationFn: (text: string) =>
      api.post<WhyInterestedResponse>(
        `/users/${userId}/jobs/${jobId}/why-interested/polish`,
        { text } satisfies PolishWhyInterestedRequest,
      ),
  });
}

export type LetterFormat = "pdf" | "docx";

export function letterDownloadUrl(
  userId: string,
  jobId: string,
  version: number,
  format: LetterFormat = "pdf",
): string {
  return `/api/users/${userId}/jobs/${jobId}/letters/${version}/download.${format}`;
}
