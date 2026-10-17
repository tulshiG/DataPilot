import { useState, useEffect, useCallback } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import KPI from "../components/KPI";
import ChartCard from "../components/ChartCard";
import { getDashboard } from "../api/dashboard";
import { getWorkspaces } from "../api/workspace";
import { getRecommendations, getAIStatus } from "../api/ai";

// ── Chart type groups for filter tabs ──────────────────────────────────────
const CHART_TABS = [
  { key: "all",       label: "All Charts",  icon: "📊" },
  { key: "line",      label: "Trends",      icon: "📈" },
  { key: "bar",       label: "Comparisons", icon: "📉" },
  { key: "pie",       label: "Shares",      icon: "🥧" },
  { key: "donut",     label: "Donuts",      icon: "🍩" },
  { key: "scatter",   label: "Correlations",icon: "🔵" },
  { key: "histogram", label: "Distributions",icon:"📦" },
  { key: "box",       label: "Box Plots",   icon: "📐" },
  { key: "heatmap",   label: "Heatmaps",    icon: "🌡️" },
  { key: "treemap",   label: "Treemaps",    icon: "🟦" },
];

// ── Domain colour map ──────────────────────────────────────────────────────
const DOMAIN_COLORS = {
  sales_orders:  "#7c6cf6",
  superstore:    "#4a90e2",
  insurance:     "#e74c3c",
  hr_employee:   "#f39c12",
  education:     "#2ecc71",
  inventory:     "#1abc9c",
  generic:       "#8b8d98",
};

const INSIGHT_ICONS = {
  query_suggestion: "💬",
  ml_suggestion: "🧠",
  data_quality: "⚠️",
  analysis_hint: "💡",
};

const INSIGHT_COLORS = {
  query_suggestion: "#8a2be2",
  ml_suggestion: "#58a6ff",
  data_quality: "#f39c12",
  analysis_hint: "#2ecc71",
};

export default function Dashboard() {
  const [workspaces, setWorkspaces]       = useState([]);
  const [activeWsId, setActiveWsId]       = useState(null);
  const [data, setData]                   = useState(null);
  const [loading, setLoading]             = useState(false);
  const [error, setError]                 = useState("");
  const [activeTab, setActiveTab]         = useState("all");
  const [activeDataset, setActiveDataset] = useState("all");
  const [searchQ, setSearchQ]             = useState("");
  const [expandedDs, setExpandedDs]       = useState({});
  const [aiInsights, setAiInsights]       = useState([]);
  const [aiStatus, setAiStatus]           = useState(null);

  // ── load workspaces once ───────────────────────────────────────────────
  useEffect(() => {
    getWorkspaces().then((res) => {
      setWorkspaces(res.data || []);
      if (res.data?.length > 0) setActiveWsId(res.data[0].id);
    }).catch(() => {});
    getAIStatus().then(res => setAiStatus(res.data)).catch(() => {});
  }, []);

  // ── load AI insights when workspace changes ────────────────────────────
  useEffect(() => {
    if (!activeWsId) return;
    getRecommendations(activeWsId)
      .then(res => setAiInsights((res.data?.recommendations || []).slice(0, 6)))
      .catch(() => {});
  }, [activeWsId]);

  // ── fetch dashboard ────────────────────────────────────────────────────
  const fetchDashboard = useCallback(async () => {
    if (!activeWsId) return;
    setLoading(true);
    setError("");
    try {
      const res = await getDashboard(activeWsId, {});
      setData(res.data);
      // expand all dataset sections by default
      const init = {};
      (res.data.datasets || []).forEach(d => { init[d.name] = true; });
      setExpandedDs(init);
    } catch {
      setError("Failed to load dashboard. Make sure the backend is running.");
    } finally {
      setLoading(false);
    }
  }, [activeWsId]);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  // ── filter charts ──────────────────────────────────────────────────────
  const allCharts = data?.charts || [];
  const filteredCharts = allCharts.filter(c => {
    const typeOk   = activeTab === "all" || c.chart_type === activeTab;
    const dsOk     = activeDataset === "all" || c.dataset_name === activeDataset;
    const searchOk = !searchQ || c.title?.toLowerCase().includes(searchQ.toLowerCase());
    return typeOk && dsOk && searchOk;
  });

  // group by dataset
  const byDataset = filteredCharts.reduce((acc, c) => {
    const key = c.dataset_name || "Other";
    if (!acc[key]) acc[key] = [];
    acc[key].push(c);
    return acc;
  }, {});

  const datasets = data?.datasets || [];
  const tabCounts = CHART_TABS.reduce((acc, t) => {
    acc[t.key] = t.key === "all" ? allCharts.length : allCharts.filter(c => c.chart_type === t.key).length;
    return acc;
  }, {});

  // Full-width chart types
  const wideTypes = new Set(["line", "heatmap"]);

  return (
    <div className="app-container">
      <Sidebar />
      <div className="dp-main">
        <Navbar title="Smart Dashboard" subtitle="Auto-detected charts for any dataset type" />

        <div className="dp-content" style={{ padding: 0, overflowY: "auto" }}>

          {/* ── Top controls bar ─────────────────────────────────────── */}
          <div style={{
            display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
            padding: "20px 32px", borderBottom: "1px solid var(--border-color)",
            background: "rgba(10,11,16,0.6)", backdropFilter: "blur(10px)",
            position: "sticky", top: 0, zIndex: 20,
          }}>
            {/* Workspace selector */}
            <select value={activeWsId || ""} onChange={e => setActiveWsId(Number(e.target.value))}
              style={{ background: "var(--bg-card)", color: "var(--text-primary)", border: "1px solid var(--border-color)", borderRadius: 8, padding: "7px 12px", fontSize: 13 }}>
              {workspaces.map(ws => <option key={ws.id} value={ws.id}>{ws.name}</option>)}
            </select>

            {/* Dataset filter */}
            <select value={activeDataset} onChange={e => setActiveDataset(e.target.value)}
              style={{ background: "var(--bg-card)", color: "var(--text-primary)", border: "1px solid var(--border-color)", borderRadius: 8, padding: "7px 12px", fontSize: 13 }}>
              <option value="all">All Datasets</option>
              {datasets.map(d => <option key={d.id} value={d.name}>{d.domain_icon} {d.name}</option>)}
            </select>

            {/* Search */}
            <input value={searchQ} onChange={e => setSearchQ(e.target.value)}
              placeholder="🔍  Search charts…"
              style={{ background: "var(--bg-card)", color: "var(--text-primary)", border: "1px solid var(--border-color)", borderRadius: 8, padding: "7px 14px", fontSize: 13, flex: 1, minWidth: 160 }} />

            {/* Refresh */}
            <button onClick={fetchDashboard} disabled={loading}
              style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 7 }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round" className={loading ? "spin" : ""}>
                <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
              {loading ? "Loading…" : "Refresh"}
            </button>
          </div>

          {error && (
            <div style={{ margin: "16px 32px", padding: "12px 16px", background: "rgba(231,76,60,0.1)", border: "1px solid rgba(231,76,60,0.3)", borderRadius: 8, color: "#e74c3c", fontSize: 13 }}>
              {error}
            </div>
          )}

          {/* Loading skeleton */}
          {loading && !data && (
            <div style={{ padding: "32px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px,1fr))", gap: 16, marginBottom: 32 }}>
                {[1,2,3,4].map(i => (
                  <div key={i} className="dp-card" style={{ height: 100, animation: "pulse 1.5s infinite" }} />
                ))}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                {[1,2,3,4].map(i => (
                  <div key={i} className="dp-card" style={{ height: 300, animation: "pulse 1.5s infinite" }} />
                ))}
              </div>
            </div>
          )}

          {data && (
            <div className="animate-fade-in" style={{ padding: "28px 32px" }}>

              {/* ── Dataset domain badges ─────────────────────────────── */}
              {datasets.length > 0 && (
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 28 }}>
                  {datasets.map(ds => (
                    <div key={ds.id} style={{
                      display: "flex", alignItems: "center", gap: 8,
                      padding: "8px 14px", borderRadius: 24,
                      background: `${DOMAIN_COLORS[ds.domain] || "#8b8d98"}12`,
                      border: `1px solid ${DOMAIN_COLORS[ds.domain] || "#8b8d98"}40`,
                      cursor: "pointer",
                      boxShadow: activeDataset === ds.name
                        ? `0 0 0 2px ${DOMAIN_COLORS[ds.domain] || "#8b8d98"}` : "none",
                    }}
                      onClick={() => setActiveDataset(v => v === ds.name ? "all" : ds.name)}>
                      <span style={{ fontSize: 18 }}>{ds.domain_icon}</span>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: DOMAIN_COLORS[ds.domain] || "#8b8d98" }}>
                          {ds.domain_label}
                        </div>
                        <div style={{ fontSize: 10, color: "#64677a" }}>
                          {ds.rows?.toLocaleString()} rows · {ds.chart_count} charts
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* ── KPI cards ─────────────────────────────────────────── */}
              {data.kpis?.length > 0 && (
                <div className="dp-kpi-grid" style={{ marginBottom: 32 }}>
                  {data.kpis.map(kpi => (
                    <KPI key={kpi.metric_id} name={kpi.name}
                      display_value={kpi.display_value} change_percent={kpi.change_percent} />
                  ))}
                </div>
              )}

              {/* ── AI Insights Panel ──────────────────────────────────── */}
              {aiInsights.length > 0 && (
                <div style={{ marginBottom: 32 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{
                        width: 28, height: 28, borderRadius: 8,
                        background: "linear-gradient(135deg, #8a2be2, #58a6ff)",
                        display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14,
                      }}>🧠</span>
                      <span style={{ fontSize: 15, fontWeight: 700, color: "var(--text-heading)" }}>
                        AI Insights
                      </span>
                      {aiStatus?.overall === "operational" && (
                        <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 10, background: "rgba(46,204,113,0.15)", color: "#2ecc71", fontWeight: 600 }}>
                          LIVE
                        </span>
                      )}
                    </div>
                    <a href="/ai-analytics" style={{ fontSize: 12, color: "var(--accent-purple)", textDecoration: "none", fontWeight: 500 }}>
                      View all →
                    </a>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
                    {aiInsights.map((insight, i) => {
                      const color = INSIGHT_COLORS[insight.type] || "#8b8d98";
                      return (
                        <div key={i} style={{
                          padding: "14px 16px", borderRadius: 10,
                          background: "var(--bg-card)", border: "1px solid var(--border-color)",
                          borderLeft: `3px solid ${color}`,
                          transition: "transform 0.2s, box-shadow 0.2s",
                          cursor: insight.suggested_query ? "pointer" : "default",
                        }}
                          onMouseOver={e => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = `0 4px 20px ${color}20`; }}
                          onMouseOut={e => { e.currentTarget.style.transform = ""; e.currentTarget.style.boxShadow = ""; }}
                          onClick={() => { if (insight.suggested_query) window.location.href = `/query`; }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                            <span style={{ fontSize: 14 }}>{INSIGHT_ICONS[insight.type] || "💡"}</span>
                            <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 6, background: `${color}18`, color, fontWeight: 600, textTransform: "uppercase" }}>
                              {(insight.type || "").replace(/_/g, " ")}
                            </span>
                          </div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-heading)", marginBottom: 4 }}>{insight.title}</div>
                          <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.4 }}>{insight.description}</div>
                          {insight.suggested_query && (
                            <div style={{ marginTop: 8, padding: "4px 8px", borderRadius: 4, background: "var(--bg-input)", fontSize: 11, color: "var(--accent-purple)", fontFamily: "monospace" }}>
                              💬 {insight.suggested_query}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* ── Chart type tabs ───────────────────────────────────── */}
              <div style={{
                display: "flex", gap: 6, flexWrap: "wrap",
                marginBottom: 24, padding: "6px",
                background: "var(--bg-card)", borderRadius: 12,
                border: "1px solid var(--border-color)",
              }}>
                {CHART_TABS.filter(t => t.key === "all" || tabCounts[t.key] > 0).map(t => (
                  <button key={t.key}
                    onClick={() => setActiveTab(t.key)}
                    style={{
                      padding: "7px 14px", borderRadius: 9,
                      background: activeTab === t.key
                        ? "linear-gradient(135deg, var(--accent-purple), var(--accent-blue))"
                        : "transparent",
                      color: activeTab === t.key ? "#fff" : "var(--text-secondary)",
                      border: "none", cursor: "pointer",
                      fontSize: 12, fontWeight: activeTab === t.key ? 600 : 500,
                      display: "flex", alignItems: "center", gap: 5,
                      transition: "all 0.2s",
                    }}>
                    {t.icon} {t.label}
                    {tabCounts[t.key] > 0 && (
                      <span style={{
                        background: activeTab === t.key ? "rgba(255,255,255,0.25)" : "var(--bg-secondary)",
                        borderRadius: 10, padding: "1px 6px", fontSize: 10,
                      }}>
                        {tabCounts[t.key]}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {/* ── Charts by dataset ─────────────────────────────────── */}
              {Object.keys(byDataset).length === 0 ? (
                <div style={{
                  textAlign: "center", padding: "64px 32px",
                  background: "var(--bg-card)", borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-color)",
                }}>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
                  <p style={{ color: "var(--text-secondary)", fontSize: 15 }}>
                    No charts match the current filter.
                  </p>
                  <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
                    Try selecting a different chart type or upload a dataset first.
                  </p>
                </div>
              ) : (
                Object.entries(byDataset).map(([dsName, charts]) => {
                  const meta = datasets.find(d => d.name === dsName);
                  const domColor = DOMAIN_COLORS[meta?.domain] || "#8b8d98";
                  const isExpanded = expandedDs[dsName] !== false;

                  return (
                    <div key={dsName} style={{ marginBottom: 44 }}>
                      {/* Section header */}
                      <div
                        onClick={() => setExpandedDs(p => ({ ...p, [dsName]: !isExpanded }))}
                        style={{
                          display: "flex", alignItems: "center", gap: 12,
                          paddingBottom: 14, marginBottom: isExpanded ? 20 : 0,
                          borderBottom: `1px solid ${domColor}30`,
                          cursor: "pointer", userSelect: "none",
                        }}>
                        <div style={{
                          width: 10, height: 10, borderRadius: "50%",
                          background: domColor, boxShadow: `0 0 8px ${domColor}`,
                        }} />
                        <span style={{ fontSize: 17, fontWeight: 700, color: "var(--text-heading)", flex: 1 }}>
                          {meta?.domain_icon || "📄"} {dsName}
                        </span>
                        {meta && (
                          <span style={{
                            fontSize: 11, padding: "3px 10px", borderRadius: 20,
                            background: `${domColor}20`, color: domColor,
                            border: `1px solid ${domColor}40`, fontWeight: 600,
                          }}>
                            {meta.domain_label}
                          </span>
                        )}
                        <span style={{ fontSize: 11, color: "#64677a" }}>
                          {charts.length} chart{charts.length !== 1 ? "s" : ""}
                        </span>
                        <span style={{ color: "#64677a", fontSize: 16, marginLeft: 4 }}>
                          {isExpanded ? "▲" : "▼"}
                        </span>
                      </div>

                      {isExpanded && (
                        <div style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))",
                          gap: 20,
                        }}>
                          {charts.map((chart, i) => (
                            <div key={i}
                              style={wideTypes.has(chart.chart_type)
                                ? { gridColumn: "1 / -1" }
                                : {}}>
                              <ChartCard chart={chart} />
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })
              )}

              {/* Footer */}
              <p style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 32, textAlign: "right" }}>
                Generated {new Date(data.generated_at).toLocaleString()} ·{" "}
                {allCharts.length} total charts across {datasets.length} dataset(s)
              </p>
            </div>
          )}

          {/* Empty state when no data yet */}
          {!data && !loading && !error && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flex: 1, padding: 64, gap: 16 }}>
              <div style={{ fontSize: 64 }}>🚀</div>
              <h2 style={{ color: "var(--text-heading)", textAlign: "center" }}>Upload a Dataset to Get Started</h2>
              <p style={{ color: "var(--text-secondary)", textAlign: "center", maxWidth: 400 }}>
                DataPilot automatically detects your dataset type — orders, insurance, students,
                HR, inventory, and more — then generates the right charts for you.
              </p>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}