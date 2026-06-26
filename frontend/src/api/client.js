const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError(
      `Can't reach the API at ${BASE_URL}. Check that the backend is running.`,
      0,
    );
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // response had no JSON body; fall back to statusText
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  startRun(config) {
    return request("/simulation/run", { method: "POST", body: JSON.stringify(config) });
  },

  getRun(runId) {
    return request(`/simulation/${runId}`);
  },

  getRunState(runId) {
    return request(`/simulation/${runId}/state`);
  },

  getNetworkMetrics(runId) {
    return request(`/analytics/${runId}/network-metrics`);
  },

  solveOptimization(runId, body = {}) {
    return request(`/optimization/${runId}/solve`, { method: "POST", body: JSON.stringify(body) });
  },

  applyRlPolicy(runId, storeIds = null) {
    return request(`/rl/${runId}/apply`, {
      method: "POST",
      body: JSON.stringify({ store_ids: storeIds }),
    });
  },

  runRlBenchmark({ numEpisodes = 20, serviceLevel = 0.95 } = {}) {
    return request(`/rl/benchmark?num_episodes=${numEpisodes}&service_level=${serviceLevel}`, {
      method: "POST",
    });
  },
};

export { ApiError };
