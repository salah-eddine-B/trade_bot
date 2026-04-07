import { useState, useEffect, useCallback } from "react";
import FilterBar from "./components/FilterBar";
import TradeTable from "./components/TradeTable";

const TRADES_URL = "/api/trades"; // proxied to backend; change to "/trades.json" for static file

export default function App() {
  const [trades, setTrades]     = useState([]);
  const [filter, setFilter]     = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const [theme, setTheme]       = useState("dark");
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchTrades = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(TRADES_URL);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // sort by time descending
      const sorted = [...data].sort(
        (a, b) => new Date(b.time) - new Date(a.time)
      );
      setTrades(sorted);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTrades(); }, [fetchTrades]);

  // toggle theme on <html>
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const filtered = filter
    ? trades.filter((t) =>
        t.symbol?.toUpperCase().includes(filter.toUpperCase())
      )
    : trades;

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>📊 Trade Dashboard</h1>
          {lastRefresh && (
            <span style={styles.subtitle}>
              Last updated: {lastRefresh.toLocaleTimeString()}
            </span>
          )}
        </div>
        <div style={styles.headerActions}>
          <FilterBar value={filter} onChange={setFilter} />
          <button style={styles.refreshBtn} onClick={fetchTrades} disabled={loading}>
            {loading ? "⏳" : "🔄"} Refresh
          </button>
          <button
            style={styles.themeBtn}
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            title="Toggle theme"
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
        </div>
      </header>

      <main style={styles.main}>
        {error && <div style={styles.error}>⚠️ Failed to load trades: {error}</div>}
        {!error && (
          <TradeTable trades={filtered} loading={loading} />
        )}
      </main>
    </div>
  );
}

const styles = {
  app: {
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    background: "var(--surface)",
    borderBottom: "1px solid var(--border)",
    padding: "16px 24px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: "12px",
    position: "sticky",
    top: 0,
    zIndex: 10,
  },
  title: {
    fontSize: "20px",
    fontWeight: 700,
    color: "var(--text)",
  },
  subtitle: {
    fontSize: "12px",
    color: "var(--muted)",
    display: "block",
    marginTop: "2px",
  },
  headerActions: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    flexWrap: "wrap",
  },
  refreshBtn: {
    background: "var(--accent)",
    color: "#fff",
    border: "none",
    borderRadius: "var(--radius)",
    padding: "8px 14px",
    cursor: "pointer",
    fontWeight: 600,
    fontSize: "13px",
    opacity: 1,
    transition: "opacity .2s",
  },
  themeBtn: {
    background: "var(--border)",
    border: "none",
    borderRadius: "var(--radius)",
    padding: "8px 10px",
    cursor: "pointer",
    fontSize: "16px",
  },
  main: {
    padding: "24px",
    flex: 1,
    overflowX: "auto",
  },
  error: {
    background: "var(--sell-bg)",
    color: "var(--sell)",
    padding: "12px 16px",
    borderRadius: "var(--radius)",
    border: "1px solid var(--sell)",
  },
};
