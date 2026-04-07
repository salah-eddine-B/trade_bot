export default function FilterBar({ value, onChange }) {
  return (
    <div style={styles.wrapper}>
      <span style={styles.icon}>🔍</span>
      <input
        style={styles.input}
        type="text"
        placeholder="Filter by symbol..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {value && (
        <button style={styles.clear} onClick={() => onChange("")} title="Clear">
          ✕
        </button>
      )}
    </div>
  );
}

const styles = {
  wrapper: {
    display: "flex",
    alignItems: "center",
    background: "var(--bg)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "0 10px",
    gap: "6px",
  },
  icon: { fontSize: "13px", color: "var(--muted)" },
  input: {
    background: "transparent",
    border: "none",
    outline: "none",
    color: "var(--text)",
    fontSize: "13px",
    padding: "8px 0",
    width: "160px",
  },
  clear: {
    background: "none",
    border: "none",
    color: "var(--muted)",
    cursor: "pointer",
    fontSize: "12px",
    padding: "2px 4px",
  },
};
