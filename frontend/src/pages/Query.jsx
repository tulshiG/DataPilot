import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import QueryExplainer from "../components/QueryExplainer";
import ChartRecommendation from "../components/ChartRecommendation";
import { askQuery, getQueryHistory } from "../api/query";
import { getWorkspaces } from "../api/workspace";
import { getDatasets } from "../api/upload";
import { getRecommendations } from "../api/ai";

export default function Query() {
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [activeDatasetId, setActiveDatasetId] = useState(""); // "" = auto-detect
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showExplainer, setShowExplainer] = useState(false);
  const [suggestions, setSuggestions] = useState([]);

  useEffect(() => {
    getWorkspaces().then((res) => {
      setWorkspaces(res.data);
      if (res.data.length > 0) setActiveWorkspaceId(res.data[0].id);
    });
  }, []);

  useEffect(() => {
    if (!activeWorkspaceId) return;
    getDatasets(activeWorkspaceId).then((res) => setDatasets(res.data)).catch(() => {});
    getQueryHistory(activeWorkspaceId).then((res) => setHistory(res.data)).catch(() => {});
    getRecommendations(activeWorkspaceId)
      .then((res) => setSuggestions(res.data?.recommendations?.filter(r => r.suggested_query) || []))
      .catch(() => {});
  }, [activeWorkspaceId]);

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim() || !activeWorkspaceId) return;
    setLoading(true);
    setError("");
    setResult(null);
    setShowExplainer(false);
    try {
      const res = await askQuery(activeWorkspaceId, question, activeDatasetId || null);
      setResult(res.data);
      if (res.data.needs_clarification) {
        setError(res.data.message + " — try: " + res.data.candidates.map(c => c.name).join(", "));
        setResult(null);
      }
      getQueryHistory(activeWorkspaceId).then((r) => setHistory(r.data));
    } catch (err) {
      setError(err.response?.data?.detail || "Could not process that query");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <Sidebar />
      <div className="dp-main">
        <Navbar title="AI Query Assistant" subtitle="Ask anything about your data in plain English" />
        <div className="dp-content query-content-wrapper">
          <div style={{ flex: 2, minWidth: 0 }} className="animate-fade-in">
            <div className="dp-card" style={{ marginBottom: 24, padding: 24 }}>
              <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
                <select
                  value={activeWorkspaceId || ""}
                  onChange={(e) => setActiveWorkspaceId(Number(e.target.value))}
                  style={{ flex: 1 }}
                >
                  {workspaces.map((ws) => <option key={ws.id} value={ws.id}>{ws.name}</option>)}
                </select>
                <select
                  value={activeDatasetId}
                  onChange={(e) => setActiveDatasetId(e.target.value)}
                  style={{ flex: 1 }}
                >
                  <option value="">🔍 Auto-detect dataset</option>
                  {datasets.map((ds) => (
                    <option key={ds.id} value={ds.id}>{ds.original_filename}</option>
                  ))}
                </select>
              </div>

              <form onSubmit={handleAsk} style={{ display: "flex", gap: 12 }}>
                <input
                  style={{ flex: 1, padding: "14px 20px", fontSize: 15 }}
                  placeholder='Ask something like "average charges" or "total sales by region"'
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                />
                <button type="submit" disabled={loading} style={{ padding: "0 28px", fontSize: 15 }}>
                  {loading ? (
                    <><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="spin"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg> Thinking...</>
                  ) : (
                    <><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2L11 13"></path><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg> Ask AI</>
                  )}
                </button>
              </form>

              {/* AI Suggestions */}
              {suggestions.length > 0 && !result && (
                <div style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  <span style={{ fontSize: 12, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
                    💡 Try:
                  </span>
                  {suggestions.slice(0, 4).map((s, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => setQuestion(s.suggested_query)}
                      style={{
                        padding: "4px 12px", borderRadius: 16, fontSize: 12,
                        background: "var(--bg-input)", border: "1px solid var(--border-color)",
                        color: "var(--accent-purple)", cursor: "pointer", transition: "all 0.2s",
                      }}
                      onMouseOver={e => e.currentTarget.style.borderColor = "var(--accent-purple)"}
                      onMouseOut={e => e.currentTarget.style.borderColor = "var(--border-color)"}
                    >
                      {s.suggested_query}
                    </button>
                  ))}
                </div>
              )}

              {error && (
                <div style={{ marginTop: 16, padding: 12, background: "rgba(231, 76, 60, 0.1)", borderRadius: 8, color: "var(--accent-red)", display: "flex", gap: 8, alignItems: "center" }}>
                  ⚠️ {error}
                </div>
              )}
            </div>

            {result && (
              <div className="dp-card animate-fade-in" style={{ padding: 32, borderTop: "4px solid var(--accent-purple)" }}>
                <h3 style={{ margin: "0 0 8px 0", fontSize: 20, color: "var(--text-heading)" }}>{result.summary}</h3>
                <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap", alignItems: "center" }}>
                  <span className="dp-badge" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)" }}>
                    Intent: <span style={{ color: "var(--accent-purple)", marginLeft: 4 }}>{result.intent}</span>
                  </span>
                  {result.engine_used && (
                    <span className="dp-badge" style={{
                      background: result.engine_used === "llm" ? "rgba(138,43,226,0.15)" : "rgba(88,166,255,0.15)",
                      border: `1px solid ${result.engine_used === "llm" ? "rgba(138,43,226,0.3)" : "rgba(88,166,255,0.3)"}`,
                    }}>
                      {result.engine_used === "llm" ? "🤖 AI Engine" : "🔤 Keyword Engine"}
                    </span>
                  )}
                  {result.confidence !== undefined && (
                    <span className="dp-badge" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)" }}>
                      Confidence: <span style={{
                        marginLeft: 4, fontWeight: 600,
                        color: result.confidence >= 0.8 ? "var(--accent-green)" : result.confidence >= 0.5 ? "var(--accent-orange)" : "var(--accent-red)",
                      }}>{Math.round(result.confidence * 100)}%</span>
                    </span>
                  )}
                  {result.row_count !== undefined && (
                    <span className="dp-badge" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)" }}>
                      {result.row_count} row{result.row_count !== 1 ? "s" : ""}
                    </span>
                  )}
                  {result.is_followup && (
                    <span className="dp-badge" style={{ background: "rgba(46,204,113,0.15)", border: "1px solid rgba(46,204,113,0.3)" }}>
                      🔗 Follow-up
                    </span>
                  )}
                </div>

                {/* Schema Corrections */}
                {result.schema_corrections && Object.keys(result.schema_corrections).length > 0 && (
                  <div style={{
                    padding: 12, borderRadius: 8, marginBottom: 16,
                    background: "rgba(243,156,18,0.1)", border: "1px solid rgba(243,156,18,0.2)",
                    fontSize: 13, color: "var(--accent-orange)",
                  }}>
                    ✏️ Auto-corrected: {Object.entries(result.schema_corrections).map(([from, to]) => `"${from}" → "${to}"`).join(", ")}
                  </div>
                )}

                {/* Data Table */}
                {result.rows?.length > 0 && (
                  <div style={{ overflowX: "auto", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-light)" }}>
                    <table style={{ width: "100%", margin: 0 }}>
                      <thead>
                        <tr>{result.columns.map((col) => <th key={col}>{col}</th>)}</tr>
                      </thead>
                      <tbody>
                        {result.rows.map((row, i) => (
                          <tr key={i}>
                            {result.columns.map((col) => (
                              <td key={col}>{row[col] !== null && row[col] !== undefined ? String(row[col]) : "—"}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Chart Recommendation */}
                <ChartRecommendation recommendation={result.chart_recommendation} />

                {/* Explainability + SQL */}
                <div style={{ marginTop: 24, display: "flex", gap: 12, flexWrap: "wrap" }}>
                  <button
                    type="button" className="secondary"
                    onClick={() => setShowExplainer(!showExplainer)}
                    style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}
                  >
                    🧠 {showExplainer ? "Hide" : "Show"} AI Reasoning
                  </button>
                  <details>
                    <summary style={{ cursor: "pointer", color: "var(--accent-purple)", fontWeight: 500, userSelect: "none", fontSize: 13 }}>View Generated SQL</summary>
                    <pre style={{ background: "var(--bg-input)", padding: 16, borderRadius: "var(--radius-sm)", overflowX: "auto", marginTop: 12, border: "1px solid var(--border-color)", fontSize: 13, color: "var(--text-primary)" }}>
                      <code>{result.generated_sql}</code>
                    </pre>
                  </details>
                </div>

                {showExplainer && <QueryExplainer explanation={result.explanation} />}
              </div>
            )}
          </div>

          {/* History Panel */}
          <div style={{ flex: 1, minWidth: 0 }} className="animate-fade-in">
            <h3 style={{ margin: "0 0 16px 0", fontSize: 16, borderBottom: "1px solid var(--border-color)", paddingBottom: 12 }}>Recent Queries</h3>
            {history.length === 0 ? (
              <p style={{ color: "var(--text-secondary)", fontSize: 14 }}>No queries yet.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {history.map((h) => (
                  <div
                    key={h.id} className="dp-card"
                    style={{ padding: 16, cursor: "pointer", transition: "transform 0.2s" }}
                    onClick={() => setQuestion(h.raw_query)}
                    onMouseOver={(e) => e.currentTarget.style.transform = "translateX(-4px)"}
                    onMouseOut={(e) => e.currentTarget.style.transform = "translateX(0)"}
                  >
                    <p style={{ margin: "0 0 8px 0", fontSize: 14, fontWeight: 500, color: "var(--text-heading)" }}>"{h.raw_query}"</p>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className={`dp-badge ${h.status === "failed" ? "error" : "success"}`} style={{ fontSize: 10, padding: "2px 6px" }}>
                        {h.status}
                      </span>
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        {new Date(h.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}