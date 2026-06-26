import { useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { usePolling } from "./usePolling";

const TERMINAL_STATUSES = new Set(["completed", "failed"]);

/**
 * The single place RunPage and its children ask "what's happening with
 * this run right now". Phase 7: polls GET /simulation/:id/state every 2s,
 * and stops once the run reaches a terminal status so a finished run
 * doesn't keep hitting the API forever. Phase 8 replaces the polling
 * underneath usePolling with a WebSocket subscription — this hook's
 * return shape ({ state, error, loading, isFinished }) is the contract
 * that doesn't change when that happens.
 */
export function useRunState(runId) {
  const [finished, setFinished] = useState(false);
  const finishedRef = useRef(false);

  const fetcher = useMemo(
    () => async () => {
      const result = await api.getRunState(runId);
      if (TERMINAL_STATUSES.has(result.status) && !finishedRef.current) {
        finishedRef.current = true;
        setFinished(true);
      }
      return result;
    },
    [runId],
  );

  const { data, error, loading } = usePolling(fetcher, { intervalMs: 2000, enabled: !finished });

  return { state: data, error, loading, isFinished: finished };
}
