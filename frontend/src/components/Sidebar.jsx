import { NavLink } from "react-router-dom";

export default function Sidebar({ recentRuns }) {
  return (
    <aside className="sidebar">
      <div style={{ padding: "22px 20px 18px", borderBottom: "1px solid var(--border)" }}>
        <p
          className="mono"
          style={{ fontSize: 11, color: "var(--accent-flow)", letterSpacing: "0.08em", marginBottom: 4 }}
        >
          SUPPLY CHAIN
        </p>
        <h1 style={{ fontSize: 17 }}>Digital Twin Console</h1>
      </div>

      <div style={{ padding: 16 }}>
        <NavLink
          to="/"
          end
          style={({ isActive }) => ({
            display: "block",
            textAlign: "center",
            padding: "10px 0",
            borderRadius: "var(--radius-sm)",
            fontWeight: 600,
            fontSize: 13,
            background: isActive ? "var(--accent-flow)" : "var(--surface-raised)",
            color: isActive ? "#07211e" : "var(--text)",
            border: "1px solid var(--border)",
          })}
        >
          + New run
        </NavLink>
      </div>

      <div style={{ padding: "0 16px", flex: 1, overflowY: "auto" }}>
        <h2 style={{ fontSize: 11, marginBottom: 10, paddingLeft: 4 }}>This session</h2>
        {recentRuns.length === 0 && (
          <p style={{ fontSize: 12, color: "var(--text-faint)", padding: "0 4px" }}>
            Runs you start will show up here.
          </p>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {recentRuns.map((run) => (
            <NavLink
              key={run.runId}
              to={`/runs/${run.runId}`}
              style={({ isActive }) => ({
                padding: "8px 10px",
                borderRadius: "var(--radius-sm)",
                background: isActive ? "var(--surface-raised)" : "transparent",
                border: isActive ? "1px solid var(--border)" : "1px solid transparent",
              })}
            >
              <span className="mono" style={{ fontSize: 12, display: "block" }}>
                {run.runId}
              </span>
              <span style={{ fontSize: 11, color: "var(--text-faint)" }}>
                {run.config.num_stores} stores · {run.config.num_steps} steps
              </span>
            </NavLink>
          ))}
        </div>
      </div>

      <div style={{ padding: 16, borderTop: "1px solid var(--border)" }}>
        <p style={{ fontSize: 11, color: "var(--text-faint)" }}>
          Phases 1-6: simulation, analytics, optimization &amp; RL.
          <br />
          Real-time updates land in Phase 8 — this console polls.
        </p>
      </div>
    </aside>
  );
}
