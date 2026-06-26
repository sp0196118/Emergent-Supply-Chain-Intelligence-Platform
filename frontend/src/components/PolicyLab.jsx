import { useState } from "react";
import { api, ApiError } from "../api/client";

export default function PolicyLab({ runId }) {
  const [tab, setTab] = useState("optimize");

  return (
    <div>
      <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
        <TabButton active={tab === "optimize"} onClick={() => setTab("optimize")} color="var(--accent-flow)">
          Optimize
        </TabButton>
        <TabButton active={tab === "learn"} onClick={() => setTab("learn")} color="var(--accent-learned)">
          Learn
        </TabButton>
      </div>

      {tab === "optimize" ? <OptimizePanel runId={runId} /> : <LearnPanel runId={runId} />}
    </div>
  );
}

function TabButton({ active, onClick, color, children }) {
  return (
    <button
      onClick={onClick}
      className="btn"
      style={{
        flex: 1,
        background: active ? color : "var(--surface-raised)",
        borderColor: active ? color : "var(--border)",
        color: active ? "#07120f" : "var(--text)",
      }}
    >
      {children}
    </button>
  );
}

function OptimizePanel({ runId }) {
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [errorMessage, setErrorMessage] = useState(null);

  async function handleOptimize() {
    setStatus("loading");
    setErrorMessage(null);
    try {
      const data = await api.solveOptimization(runId);
      setResult(data);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  }

  return (
    <div>
      <p style={{ fontSize: 12.5, color: "var(--text-dim)", marginBottom: 14 }}>
        Allocates a shared safety-stock budget across every store and distribution center
        with OR-Tools, weighted by how much of the network each one would cut off if it failed.
        Applies the result to this run — steps from here on use the optimized policy.
      </p>

      <button className="btn btn-primary" onClick={handleOptimize} disabled={status === "loading"}>
        {status === "loading" ? "Optimizing…" : "Optimize inventory"}
      </button>

      {status === "error" && (
        <p style={{ color: "var(--accent-alert)", fontSize: 12, marginTop: 10 }}>{errorMessage}</p>
      )}

      {result && (
        <div style={{ marginTop: 18 }}>
          <CostComparison
            leftLabel="Naive (same tier for everyone)"
            leftValue={result.naive_baseline_cost}
            rightLabel="OR-Tools optimized"
            rightValue={result.total_expected_stockout_cost}
            rightColor="var(--accent-flow)"
          />
          <div style={{ display: "flex", gap: 18, marginTop: 14, fontSize: 12, color: "var(--text-dim)" }}>
            <span>
              Budget used: <span className="mono">{result.budget_used.toFixed(1)}</span> /{" "}
              <span className="mono">{result.total_budget.toFixed(1)}</span>
            </span>
            <span>
              Solver: <span className="mono">{result.solver_status}</span>
            </span>
          </div>

          <h2 style={{ marginTop: 18, marginBottom: 8 }}>Policy by node</h2>
          <PolicyTable policies={result.policies} />
        </div>
      )}
    </div>
  );
}

function LearnPanel({ runId }) {
  const [result, setResult] = useState(null);
  const [applyMessage, setApplyMessage] = useState(null);
  const [status, setStatus] = useState("idle");
  const [errorMessage, setErrorMessage] = useState(null);

  async function handleBenchmark() {
    setStatus("loading");
    setErrorMessage(null);
    try {
      const data = await api.runRlBenchmark({ numEpisodes: 20 });
      setResult(data);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  }

  async function handleApply() {
    try {
      const data = await api.applyRlPolicy(runId);
      setApplyMessage(`Assigned the learned policy to ${data.stores_assigned.length} store(s) in this run.`);
    } catch (err) {
      setApplyMessage(err instanceof ApiError ? err.message : "Couldn't apply the policy.");
    }
  }

  return (
    <div>
      <p style={{ fontSize: 12.5, color: "var(--text-dim)", marginBottom: 14 }}>
        Compares the trained PPO policy against OR-Tools' reorder-point rule on a reference
        store, both deciding with the same information and facing identical demand — not this
        run's specific network, but the one the policy was trained on.
      </p>

      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn" style={{ borderColor: "var(--accent-learned)" }} onClick={handleBenchmark} disabled={status === "loading"}>
          {status === "loading" ? "Comparing…" : "Compare policies"}
        </button>
        <button className="btn" onClick={handleApply}>
          Apply to this run
        </button>
      </div>

      {status === "error" && (
        <p style={{ color: "var(--accent-alert)", fontSize: 12, marginTop: 10 }}>{errorMessage}</p>
      )}
      {applyMessage && <p style={{ fontSize: 12, marginTop: 10, color: "var(--text-dim)" }}>{applyMessage}</p>}

      {result && (
        <div style={{ marginTop: 18 }}>
          <CostComparison
            leftLabel={`OR-Tools (s,S), SL=${result.baseline_service_level}`}
            leftValue={result.baseline_avg_cost}
            rightLabel="Learned (PPO)"
            rightValue={result.ppo_avg_cost}
            rightColor="var(--accent-learned)"
          />
          <p style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 12 }}>
            Averaged over {result.num_episodes} episodes ·{" "}
            {result.improvement_pct >= 0 ? (
              <span style={{ color: "var(--accent-learned)" }}>{result.improvement_pct}% lower cost</span>
            ) : (
              <span style={{ color: "var(--accent-alert)" }}>{Math.abs(result.improvement_pct)}% higher cost</span>
            )}{" "}
            than the OR-Tools baseline.
          </p>
        </div>
      )}
    </div>
  );
}

function CostComparison({ leftLabel, leftValue, rightLabel, rightValue, rightColor }) {
  const max = Math.max(leftValue, rightValue, 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <Bar label={leftLabel} value={leftValue} max={max} color="var(--text-faint)" />
      <Bar label={rightLabel} value={rightValue} max={max} color={rightColor} />
    </div>
  );
}

function Bar({ label, value, max, color }) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, marginBottom: 4 }}>
        <span style={{ color: "var(--text-dim)" }}>{label}</span>
        <span className="mono">{value.toFixed(1)}</span>
      </div>
      <div style={{ background: "var(--bg)", borderRadius: 3, height: 9, overflow: "hidden" }}>
        <div style={{ width: `${(value / max) * 100}%`, height: "100%", background: color }} />
      </div>
    </div>
  );
}

function PolicyTable({ policies }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "var(--text-faint)" }}>
            <th style={{ padding: "4px 8px 4px 0" }}>Node</th>
            <th style={{ padding: "4px 8px" }}>Service level</th>
            <th style={{ padding: "4px 8px" }}>Reorder pt.</th>
            <th style={{ padding: "4px 8px" }}>Order up to</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((p) => (
            <tr key={p.node} style={{ borderTop: "1px solid var(--border)" }}>
              <td className="mono" style={{ padding: "5px 8px 5px 0" }}>
                {p.node}
              </td>
              <td className="mono" style={{ padding: "5px 8px" }}>
                {p.service_level}
              </td>
              <td className="mono" style={{ padding: "5px 8px" }}>
                {p.reorder_point.toFixed(1)}
              </td>
              <td className="mono" style={{ padding: "5px 8px" }}>
                {p.order_up_to.toFixed(1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
