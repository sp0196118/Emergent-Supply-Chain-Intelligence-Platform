export default function EmptyState({ title, detail, action }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
        padding: "48px 24px",
        textAlign: "center",
        color: "var(--text-dim)",
      }}
    >
      <p style={{ fontFamily: "var(--font-display)", fontSize: 15, color: "var(--text)" }}>{title}</p>
      {detail && <p style={{ fontSize: 13, maxWidth: 360 }}>{detail}</p>}
      {action}
    </div>
  );
}
