/**
 * Job-list, job-detail, refresh, and apply/unapply hooks.
 *
 * useJobs(filters) — list, with filter chips synced to URL params.
 * useJobDetail(jobId) — single job's full JD.
 * useRefreshJobs() — mutation that kicks off a background refresh.
 * useRefreshStatus(refreshId) — polls until done; pass null when no
 *   refresh is in flight (the hook short-circuits without firing).
 * useApplyJob() / useUnapplyJob() — optimistic updates so the card
 *   moves between filter tabs without waiting for the network round-trip.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";
import type {
  FetchJobUrlRequest,
  FetchJobUrlResponse,
  JobDetailResponse,
  JobListFilters,
  JobListResponse,
  ManualJobRequest,
  RefreshJobResponse,
  RefreshStatusResponse,
  SearchJobsRequest,
  SearchJobsResponse,
} from "@/lib/types";

export function useJobs(filters: JobListFilters = {}) {
  const { userId } = useAuth();
  return useQuery<JobListResponse>({
    queryKey: ["jobs", userId, filters],
    queryFn: () => api.get<JobListResponse>(`/users/${userId}/jobs`, filters),
    enabled: Boolean(userId),
  });
}

export function useJobDetail(jobId: string | undefined) {
  const { userId } = useAuth();
  return useQuery<JobDetailResponse>({
    queryKey: ["job", userId, jobId],
    queryFn: () =>
      api.get<JobDetailResponse>(`/users/${userId}/jobs/${jobId}`),
    enabled: Boolean(userId && jobId),
  });
}

export function useRefreshJobs() {
  const { userId } = useAuth();
  return useMutation({
    mutationFn: () =>
      api.post<RefreshJobResponse>(`/users/${userId}/jobs/refresh`),
  });
}

export function useRefreshStatus(refreshId: string | null) {
  const { userId } = useAuth();
  return useQuery<RefreshStatusResponse>({
    queryKey: ["refresh", userId, refreshId],
    queryFn: () =>
      api.get<RefreshStatusResponse>(
        `/users/${userId}/jobs/refresh/${refreshId}`,
      ),
    enabled: Boolean(userId && refreshId),
    // Poll every 3s while the refresh is in flight; stop once it's done.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "failed" ? false : 3000;
    },
  });
}

export function useSearchJobs() {
  const { userId } = useAuth();
  return useMutation({
    mutationFn: (spec: SearchJobsRequest) =>
      api.post<SearchJobsResponse>(`/users/${userId}/jobs/search`, spec),
  });
}

export function useSearchStatus(searchId: string | null) {
  const { userId } = useAuth();
  return useQuery<RefreshStatusResponse>({
    queryKey: ["search", userId, searchId],
    queryFn: () =>
      api.get<RefreshStatusResponse>(
        `/users/${userId}/jobs/search/${searchId}`,
      ),
    enabled: Boolean(userId && searchId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "failed" ? false : 2000;
    },
  });
}

export function useApplyJob() {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      api.post<void>(`/users/${userId}/jobs/${jobId}/applied`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", userId] });
    },
  });
}

export function useUnapplyJob() {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      api.del<void>(`/users/${userId}/jobs/${jobId}/applied`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", userId] });
    },
  });
}

// ----- Manually-added jobs -----

export function useFetchJobUrl() {
  const { userId } = useAuth();
  return useMutation({
    mutationFn: (url: string) =>
      api.post<FetchJobUrlResponse>(
        `/users/${userId}/jobs/manual/fetch`,
        { url } satisfies FetchJobUrlRequest,
      ),
  });
}

export function useCreateManualJob() {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ManualJobRequest) =>
      api.post<JobDetailResponse>(`/users/${userId}/jobs/manual`, body),
    onSuccess: () => {
      // Refresh both the manual list and the broader jobs cache so the
      // new job shows up wherever it can appear.
      queryClient.invalidateQueries({ queryKey: ["manual-jobs", userId] });
      queryClient.invalidateQueries({ queryKey: ["applications", userId] });
    },
  });
}

export function useManualJobs() {
  const { userId } = useAuth();
  return useQuery<JobListResponse>({
    queryKey: ["manual-jobs", userId],
    queryFn: () =>
      api.get<JobListResponse>(`/users/${userId}/jobs/manual`),
    enabled: Boolean(userId),
  });
}
