/**
 * useGlobalHiddenPublishers — admin-managed global list applied to
 * every user's job-snapshot filtering.
 *
 * Read is open to any authenticated caller (the rendered Settings
 * card is admin-only, but the ranking pipeline also needs the
 * value). Write is admin-only — the backend returns 403 for non-
 * admin tokens.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  GlobalHiddenPublishersResponse,
  UpdateGlobalHiddenPublishersRequest,
} from "@/lib/types";

const KEY = ["global", "hidden-publishers"] as const;

export function useGlobalHiddenPublishers() {
  return useQuery<GlobalHiddenPublishersResponse>({
    queryKey: KEY,
    queryFn: () =>
      api.get<GlobalHiddenPublishersResponse>("/global/hidden-publishers"),
  });
}

export function useUpdateGlobalHiddenPublishers() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (items: string[]) =>
      api.put<GlobalHiddenPublishersResponse>("/global/hidden-publishers", {
        items,
      } satisfies UpdateGlobalHiddenPublishersRequest),
    onSuccess: (data) => {
      queryClient.setQueryData(KEY, data);
    },
  });
}
