export default function TradeRow({ trade }) {
  const isBuy = trade.action?.toUpperCase() === "BUY";
  const tp    = Array.isArray(trade.tp) ? trade.tp[0] : trade.tp;

  const rowStyle = {
    background: isBuy ? "var(--buy-bg)" : "var(--sell-bg)",
    borderBottom: "1px solid var(--border)",
    transition: "filter .15s",
  };

  const fmt = (n) => (n != null ? Number(n).toFixed(5) : "—");
  const fmtLot = (n) => (n != null ? Number(n).toFixed(2) : "—");

  return (
    <tr style={rowStyle} className="trade-row">
      <td style={styles.td}>{trade.time ?? "—"}</td>
      <td style={{ ...styles.td, fontWeight: 700 }}>{trade.symbol ?? "—"}</td>
      <td style={{ ...styles.td }}>
        <span style={{ ...styles.badge, background: isBuy ? "var(--buy)" : "var(--sell)" }}>
          {trade.action ?? "—"}
        </span>
      </td>
      <td style={styles.td}>{fmt(trade.entry)}</td>
      <td style={{ ...styles.td, color: "var(--sell)" }}>{fmt(trade.sl)}</td>
      <td style={{ ...styles.td, color: "var(--buy)" }}>{fmt(tp)}</td>
      <td style={styles.td}>{fmtLot(trade.lot)}</td>
    </tr>
  );
}

const styles = {
  td: {
    padding: "10px 14px",
    color: "var(--text)",
    whiteSpace: "nowrap",
  },
  badge: {
    display: "inline-block",
    padding: "2px 10px",
    borderRadius: "999px",
    color: "#fff",
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: ".5px",
  },
};
