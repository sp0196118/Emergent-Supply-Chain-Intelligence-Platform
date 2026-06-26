import { useRunState } from "../hooks/useRunState";
import EmptyState from "./EmptyState";

const KIND_LABEL = { supplier: "Suppliers", distribution_center: "Distribution centers", store: "Stores" };
const KIND_ORDER = ["supplier", "distribution_center", "store"];

function groupByKind(inventoryLevels, nodes) {
  const kindOf = new Map(nodes.map((n) => [n.id, n.kind]));
  const groups = { supplier: [], distribution_center: [], store: [] };
  Object.entries(inventoryLevels).forEach(([id, value]) => {
    const kind = kindOf.get(id);
    if (kind) groups[kind].push({ id, value });
  });
  Object.values(groups).forEach((list) => list.sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true })));
  return groups;
}

export default function InventorySnapshot({ runId, metrics }) {
  const { state, error, loading, isFinished } = useRunState(runId);

  if (error) {
    return <EmptyState title="Couldn't load inventory" detail={error.message} />;
  }
  if (loading && !state) {
    return <EmptyState title="Loading inventory snapshot…" />;
  }

  const groups = groupByKind(state.inventory_levels, metrics.nodes);
  const stockoutSet = new Set(state.stockouts);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 14 }}>
        <p className="mono" style={{ fontSize: 12, color: "var(--text-dim)" }}>
          Step {state.step}
        </p>
        {!isFinished && (
          <p style={{ fontSize: 11, color: "var(--text-faint)" }}>Updating every 2s</p>
        )}
      </div>

      {state.stockouts.length > 0 && (
        <p style={{ fontSize: 12, color: "var(--accent-alert)", marginBottom: 14 }}>
          {state.stockouts.length} store{state.stockouts.length > 1 ? "s" : ""} out of stock this step
        </p>
      )}

      {KIND_ORDER.map((kind) => {
        const items = groups[kind];
        if (items.length === 0) return null;
        const max = Math.max(...items.map((i) => i.value), 1);
        return (
          <div key={kind} style={{ marginBottom: 16 }}>
            <h2 style={{ fontSize: 11, marginBottom: 8 }}>{KIND_LABEL[kind]}</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {items.map((item) => {
                const isOut = stockoutSet.has(item.id);
                return (
                  <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className="mono" style={{ fontSize: 11, color: "var(--text-dim)", width: 70, flex: "none" }}>
                      {item.id}
                    </span>
                    <div style={{ flex: 1, background: "var(--bg)", borderRadius: 3, height: 8, overflow: "hidden" }}>
                      <div
                        style={{
                          width: `${Math.min(100, (item.value / max) * 100)}%`,
                          height: "100%",
                          background: isOut ? "var(--accent-alert)" : "var(--accent-flow)",
                        }}
                      />
                    </div>
                    <span className="mono" style={{ fontSize: 11, width: 48, textAlign: "right", flex: "none" }}>
                      {item.value.toFixed(0)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
