import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { RunCreate } from "./types";

export const queryKeys = {
  catalog: ["catalog"] as const,
  currentRun: ["run", "current"] as const,
  metrics: ["metrics"] as const,
  profile: ["profile"] as const,
  sessions: ["sessions"] as const,
  session: (id: string) => ["sessions", id] as const,
};

export const useCatalog = () =>
  useQuery({ queryKey: queryKeys.catalog, queryFn: api.catalog, staleTime: Infinity });

export const useProfile = () =>
  useQuery({ queryKey: queryKeys.profile, queryFn: api.profile, staleTime: Infinity });

/** Polled as a fallback; the event stream keeps the live view current. */
export const useCurrentRun = () =>
  useQuery({ queryKey: queryKeys.currentRun, queryFn: api.currentRun, refetchInterval: 5000 });

export const useMetrics = (live: boolean) =>
  useQuery({
    queryKey: queryKeys.metrics,
    queryFn: api.metrics,
    refetchInterval: live ? 1000 : false,
  });

export const useSessions = () => useQuery({ queryKey: queryKeys.sessions, queryFn: api.sessions });

export const useSession = (sessionId: string | null) =>
  useQuery({
    queryKey: queryKeys.session(sessionId ?? ""),
    queryFn: () => api.session(sessionId ?? ""),
    enabled: sessionId !== null,
  });

function useRunMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSettled: () => {
      void client.invalidateQueries({ queryKey: queryKeys.currentRun });
      void client.invalidateQueries({ queryKey: queryKeys.metrics });
      void client.invalidateQueries({ queryKey: queryKeys.sessions });
    },
  });
}

export const useStartRun = () => useRunMutation((body: RunCreate) => api.startRun(body));
export const useStopRun = () => useRunMutation((runId: string) => api.stopRun(runId));
export const useResetRun = () => useRunMutation((runId: string) => api.resetRun(runId));
export const useInjectFault = () =>
  useRunMutation(({ runId, fault }: { runId: string; fault: string }) =>
    api.injectFault(runId, fault),
  );
