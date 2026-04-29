/**
 * App-wide TanStack Query client.
 *
 * Defaults tuned for our use case:
 * - staleTime: 30s — cached data is "fresh" briefly so quick navigation
 *   doesn't refetch unnecessarily.
 * - retry: 1 — one auto-retry on failure; beyond that, surface the
 *   error to the user.
 * - refetchOnWindowFocus: false — refetching when the tab regains
 *   focus is annoying for an app where the user knows when data is
 *   stale (refresh button is explicit).
 */

import { QueryClient } from "@tanstack/react-query";

import { ApiClientError } from "@/lib/api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => {
        // Don't retry 4xx errors — they're not transient.
        if (error instanceof ApiClientError && error.status < 500) {
          return false;
        }
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
});
