const COLUMN_X = { supplier: 70, distribution_center: 340, store: 610 };
const COLUMN_LABEL = { supplier: "Suppliers", distribution_center: "Distribution centers", store: "Stores" };
const ROW_HEIGHT = 46;
const TOP_PAD = 50;

function layout(nodes) {
  const byKind = { supplier: [], distribution_center: [], store: [] };
  nodes.forEach((n) => byKind[n.kind]?.push(n));

  const positioned = {};
  Object.entries(byKind).forEach(([kind, list]) => {
    list.forEach((node, i) => {
      positioned[node.id] = { x: COLUMN_X[kind], y: TOP_PAD + i * ROW_HEIGHT, kind };
    });
  });
  return { positioned, byKind };
}

export default function NetworkTopology({ metrics }) {
  const { positioned, byKind } = layout(metrics.nodes);
  const bottleneckByNode = new Map(metrics.bottlenecks.map((b) => [b.node, b]));
  const maxRows = Math.max(byKind.supplier.length, byKind.distribution_center.length, byKind.store.length, 1);
  const height = TOP_PAD + maxRows * ROW_HEIGHT + 20;

  return (
    <div>
      <svg viewBox={`0 0 680 ${height}`} width="100%" height={height} role="img" aria-label="Supply chain network topology">
        {Object.entries(COLUMN_X).map(([kind, x]) => (
          <text
            key={kind}
            x={x}
            y={24}
            textAnchor="middle"
            className="mono"
            fontSize="10"
            fill="var(--text-faint)"
            style={{ textTransform: "uppercase", letterSpacing: "0.06em" }}
          >
            {COLUMN_LABEL[kind]}
          </text>
        ))}

        {metrics.edges.map((edge, i) => {
          const from = positioned[edge.source];
          const to = positioned[edge.target];
          if (!from || !to) return null;
          return (
            <path
              key={i}
              d={`M ${from.x + 16} ${from.y} C ${(from.x + to.x) / 2} ${from.y}, ${(from.x + to.x) / 2} ${to.y}, ${to.x - 16} ${to.y}`}
              fill="none"
              stroke="var(--accent-flow-dim)"
              strokeWidth="1.5"
            />
          );
        })}

        {metrics.nodes.map((node) => {
          const pos = positioned[node.id];
          const bottleneck = bottleneckByNode.get(node.id);
          const color = bottleneck ? "var(--accent-alert)" : "var(--accent-flow)";
          const radius = node.kind === "store" ? 7 : 10;
          return (
            <g key={node.id}>
              <circle cx={pos.x} cy={pos.y} r={radius} fill="var(--surface)" stroke={color} strokeWidth="2">
                <title>
                  {node.id}
                  {bottleneck ? ` — losing this cuts off ${bottleneck.stores_cut_off_pct}% of stores` : ""}
                </title>
              </circle>
              <text x={pos.x + radius + 8} y={pos.y + 4} className="mono" fontSize="10.5" fill="var(--text-dim)">
                {node.id}
              </text>
            </g>
          );
        })}
      </svg>

      <div style={{ display: "flex", gap: 18, marginTop: 8, fontSize: 11, color: "var(--text-dim)" }}>
        <Legend color="var(--accent-flow)" label="Healthy" />
        <Legend color="var(--accent-alert)" label="Single point of failure" />
      </div>
    </div>
  );
}

function Legend({ color, label }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", border: `2px solid ${color}`, display: "inline-block" }} />
      {label}
    </span>
  );
}
