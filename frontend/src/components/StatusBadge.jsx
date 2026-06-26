const STATUS_STYLES = {
  queued: { color: "var(--text-dim)", label: "Queued" },
  running: { color: "var(--accent-flow)", label: "Running" },
  completed: { color: "var(--accent-flow)", label: "Completed" },
  failed: { color: "var(--accent-alert)", label: "Failed" },
};

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.queued;
  return (
    <span className="badge" style={{ borderColor: style.color, color: style.color }}>
      <span className="badge-dot" style={{ background: style.color }} />
      {style.label}
    </span>
  );
}
