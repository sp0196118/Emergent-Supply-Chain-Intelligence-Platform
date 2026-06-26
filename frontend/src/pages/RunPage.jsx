import { useParams } from "react-router-dom";
import { useNetworkMetrics } from "../hooks/useNetworkMetrics";
import { useRunState } from "../hooks/useRunState";
import NetworkTopology from "../components/NetworkTopology";
import InventorySnapshot from "../components/InventorySnapshot";
import PolicyLab from "../components/PolicyLab";
import StatusBadge from "../components/StatusBadge";
import EmptyState from "../components/EmptyState";

export default function RunPage() {
  const { runId } = useParams();
  const { metrics, error: metricsError } = useNetworkMetrics(runId);
  const { state } = useRunState(runId);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 24 }}>
        <h1 className="mono">{runId}</h1>
        {state && <StatusBadge status={state.status} />}
        {state && (
          <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
            Step <span className="mono">{state.step}</span>
          </span>
        )}
      </div>

      <div className="panel" style={{ marginBottom: 20 }}>
        <h2 style={{ marginBottom: 14 }}>Network topology</h2>
        {metricsError ? (
          <EmptyState
            title="Couldn't load the network"
            detail={metricsError.message}
          />
        ) : metrics ? (
          <NetworkTopology metrics={metrics} />
        ) : (
          <EmptyState title="Loading network topology…" />
        )}
      </div>

      <div className="run-columns">
        <div className="panel">
          <h2 style={{ marginBottom: 14 }}>Inventory snapshot</h2>
          {metrics && <InventorySnapshot runId={runId} metrics={metrics} />}
        </div>
        <div className="panel">
          <h2 style={{ marginBottom: 14 }}>Policy lab</h2>
          <PolicyLab runId={runId} />
        </div>
      </div>
    </div>
  );
}
