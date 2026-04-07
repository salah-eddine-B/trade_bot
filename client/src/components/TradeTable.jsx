import TradeRow from "./TradeRow";

const COLUMNS = ["Time", "Symbol", "Action", "Entry", "SL", "TP1", "Lot"];

export default function TradeTable({ trades, loading }) {
  if (loading) {
    return <div style={styles.center}>⏳ Loading trades...</div>;
  }

  if (!trades.length) {
    return <div style={styles.center}>No trades found.</div>;
  }

  return (
    <div style={styles.wrapper}>
      <div style={styles.meta}>{trades.length} trade{trades.length !== 1 ? "s" : ""}</div>
      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr style={styles.headRow}>
              {COLUMNS.map((col) => (
                <th key={col} style={styles.th}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.map((trade, i) => (
              <TradeRow key={trade.ticket ?? i} trade={trade} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const styles = {
  wrapper: { display: "flex", flexDirection: "column", gap: "8px" },
  meta: { fontSize: "12px", color: "var(--muted)" },
  tableWrapper: {
    overflowX: "auto",
    borderRadius: "var(--radius)",
    border: "1px solid var(--border)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    background: "var(--surface)",
  },
  headRow: {
    background: "var(--surface)",
    borderBottom: "2px solid var(--border)",
  },
  th: {
    padding: "10px 14px",
    textAlign: "left",
    fontWeight: 600,
    color: "var(--muted)",
    fontSize: "12px",
    textTransform: "uppercase",
    letterSpacing: ".5px",
    whiteSpace: "nowrap",
  },
  center: {
    textAlign: "center",
    padding: "48px",
    color: "var(--muted)",
    fontSize: "15px",
  },
};
