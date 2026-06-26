import { useEffect, useState } from "react";
import { api } from "../api/client";

/**
 * Network topology is static for the lifetime of a run (Phase 3's model
 * doesn't change its node/edge structure mid-run), so this fetches once
 * rather than polling. Both NetworkTopology and InventorySnapshot need
 * each node's kind (supplier/distribution_center/store) for grouping —
 * fetching it once here and passing it down means neither component has
 * to guess a node's kind from its name string.
 */
export function useNetworkMetrics(runId) {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getNetworkMetrics(runId)
      .then((data) => !cancelled && setMetrics(data))
      .catch((err) => !cancelled && setError(err));
    return () => {
      cancelled = true;
    };
  }, [runId]);

  return { metrics, error };
}
