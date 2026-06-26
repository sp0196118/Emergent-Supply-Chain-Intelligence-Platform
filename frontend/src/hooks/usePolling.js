import { useEffect, useRef, useState } from "react";

/**
 * Polls an async fetcher on an interval and exposes {data, error, loading}.
 *
 * This is Phase 7's stand-in for real-time updates — REST polling, not a
 * push subscription. Phase 8 replaces the inside of this hook with a
 * WebSocket listener; every component below calls useRunState (not this
 * hook directly) and reads the same {data, error, loading} shape, so that
 * swap shouldn't require touching NetworkTopology, InventorySnapshot, or
 * RunPage at all.
 */
export function usePolling(fetcher, { intervalMs = 2000, enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timeoutId;

    async function tick() {
      try {
        const result = await fetcherRef.current();
        if (!cancelled) {
          setData(result);
          setError(null);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err);
          setLoading(false);
        }
      }
      if (!cancelled) {
        timeoutId = setTimeout(tick, intervalMs);
      }
    }

    setLoading(true);
    tick();

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, enabled]);

  return { data, error, loading };
}
