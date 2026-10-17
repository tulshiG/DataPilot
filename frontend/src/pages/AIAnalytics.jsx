import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import { getWorkspaces } from "../api/workspace";
import { getDatasets } from "../api/upload";
import {
  runForecast, detectAnomalies, runSegmentation,
  getRecommendations, getKnowledgeGraph, getSemanticLayer,
} from "../api/ai";

export default function AIAnalytics() {
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [activeDatasetId, setActiveDatasetId] = useState("");
  const [activeTab, setActiveTab] = useState("recommendations");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [recommendations, setRecommendations] = useState([]);

  // Forecast params
  const [forecastDateCol, setForecastDateCol] = useState("");
  const [forecastValueCol, setForecastValueCol] = useState("");
  const [forecastPeriods, setForecastPeriods] = useState(12);

  // Anomaly params
  const [anomalyMethod, setAnomalyMethod] = useState("auto");

  // Segmentation params
  const [segmentClusters, setSegmentClusters] = useState("");

  useEffect(() => {
    getWorkspaces().then((res) => {
      setWorkspaces(res.data);
      if (res.data.length > 0) setActiveWorkspaceId(res.data[0].id);
    });
  }, []);

  useEffect(() => {
    if (!activeWorkspaceId) return;
    getDatasets(activeWorkspaceId).then((res) => {
      const processed = res.data.filter(d => d.is_processed === 1);
      setDatasets(processed);
      if (processed.length > 0 && !activeDatasetId) setActiveDatasetId(String(processed[0].id));
    }).catch(() => {});
    getRecommendations(activeWorkspaceId)
      .then((res) => setRecommendations(res.data?.recommendations || []))
      .catch(() => {});
  }, [activeWorkspaceId]);

  const tabs = [
    { id: "recommendations", label: "💡 Recommendations", icon: "💡" },
    { id: "forecast", label: "📈 Forecasting", icon: "📈" },
    { id: "anomalies", label: "🔍 Anomaly Detection", icon: "🔍" },
    { id: "segments", label: "👥 Segmentation", icon: "👥" },
    { id: "knowledge", label: "🕸️ Knowledge Graph", icon: "🕸️" },
    { id: "semantic", label: "📊 Semantic Layer", icon: "📊" },
  ];

  const handleRunForecast = async () => {
    if (!activeDatasetId || !forecastDateCol || !forecastValueCol) return;
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await runForecast(activeDatasetId, forecastDateCol, forecastValueCol, forecastPeriods);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Forecast failed");
    } finally { setLoading(false); }
  };

  const handleRunAnomalies = async () => {
    if (!activeDatasetId) return;
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await detectAnomalies(activeDatasetId, null, anomalyMethod);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Anomaly detection failed");
    } finally { setLoading(false); }
  };

  const handleRunSegmentation = async () => {
    if (!activeDatasetId) return;
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await runSegmentation(activeDatasetId, null, segmentClusters ? Number(segmentClusters) : null);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Segmentation failed");
    } finally { setLoading(false); }
  };

  const handleLoadGraph = async () => {
    if (!activeWorkspaceId) return;
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await getKnowledgeGraph(activeWorkspaceId);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load knowledge graph");
    } finally { setLoading(false); }
  };

  const handleLoadSemantic = async () => {
    if (!activeWorkspaceId) return;
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await getSemanticLayer(activeWorkspaceId);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load semantic layer");
    } finally { setLoading(false); }
  };

  useEffect(() => {
    setResult(null); setError("");
    if (activeTab === "knowledge") handleLoadGraph();
    if (activeTab === "semantic") handleLoadSemantic();
  }, [activeTab]);

  const datasetColumns = datasets.find(d => String(d.id) === activeDatasetId)?.columns || [];

  return (
    <div className="app-container">
      <Sidebar />
      <div className="dp-main">
        <Navbar title="AI Analytics" subtitle="Machine learning insights and predictive analytics" />
        <div className="dp-content" style={{ padding: 24 }}>
          {/* Workspace + Dataset selectors */}
          <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
            <select value={activeWorkspaceId || ""} onChange={(e) => setActiveWorkspaceId(Number(e.target.value))} style={{ flex: 1 }}>
              {workspaces.map((ws) => <option key={ws.id} value={ws.id}>{ws.name}</option>)}
            </select>
            <select value={activeDatasetId} onChange={(e) => setActiveDatasetId(e.target.value)} style={{ flex: 1 }}>
              <option value="">Select a dataset</option>
              {datasets.map((ds) => <option key={ds.id} value={ds.id}>{ds.original_filename}</option>)}
            </select>
          </div>

          {/* Tab Bar */}
          <div style={{ display: "flex", gap: 4, marginBottom: 24, overflowX: "auto", paddingBottom: 4 }}>
            {tabs.map((tab) => (
              <button
                key={tab.id}
                className={activeTab === tab.id ? "" : "secondary"}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: "10px 20px", borderRadius: 8, fontSize: 13, fontWeight: 500,
                  whiteSpace: "nowrap", transition: "all 0.2s",
                  ...(activeTab === tab.id ? {
                    background: "linear-gradient(135deg, var(--accent-purple), var(--accent-blue, #58a6ff))",
                    border: "none", color: "#fff",
                  } : {}),
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {error && (
            <div style={{ padding: 12, borderRadius: 8, background: "rgba(231,76,60,0.1)", color: "var(--accent-red)", marginBottom: 16, fontSize: 13 }}>
              ⚠️ {error}
            </div>
          )}

          {/* === RECOMMENDATIONS === */}
          {activeTab === "recommendations" && (
            <div className="animate-fade-in">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
                {recommendations.map((rec, i) => (
                  <div key={i} className="dp-card" style={{ padding: 20, borderLeft: `4px solid ${priorityColor(rec.priority)}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                      <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 8, background: typeBackground(rec.type), color: typeColor(rec.type) }}>
                        {rec.type.replace(/_/g, " ")}
                      </span>
                      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Priority: {rec.priority}/5</span>
                    </div>
                    <h4 style={{ margin: "0 0 6px 0", fontSize: 14, color: "var(--text-heading)" }}>{rec.title}</h4>
                    <p style={{ margin: 0, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{rec.description}</p>
                    {rec.suggested_query && (
                      <div style={{ marginTop: 12, padding: "6px 12px", borderRadius: 6, background: "var(--bg-input)", fontSize: 12, color: "var(--accent-purple)", fontFamily: "monospace" }}>
                        💬 {rec.suggested_query}
                      </div>
                    )}
                  </div>
                ))}
                {recommendations.length === 0 && (
                  <div style={{ gridColumn: "1 / -1", textAlign: "center", padding: 60, color: "var(--text-muted)" }}>
                    <p style={{ fontSize: 36, margin: "0 0 12px 0" }}>💡</p>
                    <p>Upload and process a dataset to get AI-powered recommendations.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* === FORECASTING === */}
          {activeTab === "forecast" && (
            <div className="animate-fade-in">
              <div className="dp-card" style={{ padding: 24, marginBottom: 24 }}>
                <h3 style={{ margin: "0 0 16px 0", fontSize: 16, color: "var(--text-heading)" }}>📈 Time-Series Forecasting</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 12, alignItems: "end" }}>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>Date Column</label>
                    <input value={forecastDateCol} onChange={e => setForecastDateCol(e.target.value)} placeholder="e.g. order_date" style={{ width: "100%" }} />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>Value Column</label>
                    <input value={forecastValueCol} onChange={e => setForecastValueCol(e.target.value)} placeholder="e.g. revenue" style={{ width: "100%" }} />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>Periods</label>
                    <input type="number" value={forecastPeriods} onChange={e => setForecastPeriods(Number(e.target.value))} min={1} max={60} style={{ width: "100%" }} />
                  </div>
                  <button onClick={handleRunForecast} disabled={loading} style={{ padding: "10px 24px" }}>
                    {loading ? "Running..." : "Run Forecast"}
                  </button>
                </div>
              </div>
              {result && result.status === "success" && <ForecastResult data={result} />}
            </div>
          )}

          {/* === ANOMALY DETECTION === */}
          {activeTab === "anomalies" && (
            <div className="animate-fade-in">
              <div className="dp-card" style={{ padding: 24, marginBottom: 24 }}>
                <h3 style={{ margin: "0 0 16px 0", fontSize: 16, color: "var(--text-heading)" }}>🔍 Anomaly Detection</h3>
                <div style={{ display: "flex", gap: 12, alignItems: "end" }}>
                  <div style={{ flex: 1 }}>
                    <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>Method</label>
                    <select value={anomalyMethod} onChange={e => setAnomalyMethod(e.target.value)} style={{ width: "100%" }}>
                      <option value="auto">Auto-detect</option>
                      <option value="iqr">IQR (Statistical)</option>
                      <option value="zscore">Z-Score</option>
                      <option value="isolation_forest">Isolation Forest (ML)</option>
                    </select>
                  </div>
                  <button onClick={handleRunAnomalies} disabled={loading} style={{ padding: "10px 24px" }}>
                    {loading ? "Scanning..." : "Detect Anomalies"}
                  </button>
                </div>
              </div>
              {result && result.status === "success" && <AnomalyResult data={result} />}
            </div>
          )}

          {/* === SEGMENTATION === */}
          {activeTab === "segments" && (
            <div className="animate-fade-in">
              <div className="dp-card" style={{ padding: 24, marginBottom: 24 }}>
                <h3 style={{ margin: "0 0 16px 0", fontSize: 16, color: "var(--text-heading)" }}>👥 Customer Segmentation</h3>
                <div style={{ display: "flex", gap: 12, alignItems: "end" }}>
                  <div style={{ flex: 1 }}>
                    <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>Clusters (auto if empty)</label>
                    <input type="number" value={segmentClusters} onChange={e => setSegmentClusters(e.target.value)} placeholder="Auto" min={2} max={10} style={{ width: "100%" }} />
                  </div>
                  <button onClick={handleRunSegmentation} disabled={loading} style={{ padding: "10px 24px" }}>
                    {loading ? "Clustering..." : "Run Segmentation"}
                  </button>
                </div>
              </div>
              {result && result.status === "success" && <SegmentResult data={result} />}
            </div>
          )}

          {/* === KNOWLEDGE GRAPH === */}
          {activeTab === "knowledge" && (
            <div className="animate-fade-in">
              {result && !result.error && <KnowledgeGraphResult data={result} />}
              {result && result.error && <p style={{ color: "var(--text-muted)" }}>{result.error}</p>}
              {loading && <p style={{ color: "var(--text-muted)" }}>Loading graph...</p>}
            </div>
          )}

          {/* === SEMANTIC LAYER === */}
          {activeTab === "semantic" && (
            <div className="animate-fade-in">
              {result && !result.error && <SemanticResult data={result} />}
              {result && result.error && <p style={{ color: "var(--text-muted)" }}>{result.error}</p>}
              {loading && <p style={{ color: "var(--text-muted)" }}>Loading semantic layer...</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ──────── Sub-components ──────── */

function ForecastResult({ data }) {
  return (
    <div className="dp-card" style={{ padding: 24 }}>
      <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        <MetricCard label="Trend" value={data.trend} color={data.trend === "increasing" ? "var(--accent-green)" : data.trend === "decreasing" ? "var(--accent-red)" : "var(--accent-orange)"} />
        <MetricCard label="Slope" value={data.trend_slope?.toFixed(4)} />
        <MetricCard label="Seasonality" value={data.seasonality_detected ? "Detected ✓" : "None"} color={data.seasonality_detected ? "var(--accent-purple)" : "var(--text-muted)"} />
        <MetricCard label="Method" value={data.method_used?.replace(/_/g, " ")} />
      </div>
      {data.forecast?.length > 0 && (
        <div style={{ overflowX: "auto", borderRadius: 8, border: "1px solid var(--border-light)" }}>
          <table style={{ width: "100%", margin: 0 }}>
            <thead><tr><th>Date</th><th>Predicted</th><th>Lower Bound</th><th>Upper Bound</th></tr></thead>
            <tbody>
              {data.forecast.map((f, i) => (
                <tr key={i}>
                  <td>{f.date}</td>
                  <td style={{ fontWeight: 600, color: "var(--accent-purple)" }}>{f.predicted}</td>
                  <td style={{ color: "var(--text-muted)" }}>{f.lower}</td>
                  <td style={{ color: "var(--text-muted)" }}>{f.upper}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AnomalyResult({ data }) {
  return (
    <div className="dp-card" style={{ padding: 24 }}>
      <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        <MetricCard label="Anomalies Found" value={data.anomaly_count} color={data.anomaly_count > 0 ? "var(--accent-red)" : "var(--accent-green)"} />
        <MetricCard label="Anomaly Rate" value={`${data.anomaly_rate}%`} />
        <MetricCard label="Total Rows" value={data.total_rows} />
        <MetricCard label="Method" value={data.method_used?.replace(/_/g, " ")} />
      </div>
      {data.column_anomalies && (
        <div>
          <h4 style={{ margin: "0 0 12px 0", fontSize: 14, color: "var(--text-heading)" }}>Per-Column Analysis</h4>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: 12 }}>
            {Object.entries(data.column_anomalies).map(([col, info]) => (
              <div key={col} style={{ padding: 16, borderRadius: 8, background: "var(--bg-input)", border: "1px solid var(--border-color)" }}>
                <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text-heading)", marginBottom: 6 }}>{col}</div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                  {info.anomaly_count} anomalie{info.anomaly_count !== 1 ? "s" : ""}
                  {info.lower_bound !== undefined && ` · Bounds: [${info.lower_bound}, ${info.upper_bound}]`}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SegmentResult({ data }) {
  const clusterColors = ["#8a2be2", "#58a6ff", "#2ecc71", "#f39c12", "#e74c3c", "#1abc9c", "#e67e22", "#9b59b6"];
  return (
    <div className="dp-card" style={{ padding: 24 }}>
      <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        <MetricCard label="Clusters" value={data.optimal_k} color="var(--accent-purple)" />
        <MetricCard label="Total Rows" value={data.total_rows} />
        <MetricCard label="Features Used" value={data.features_used?.length} />
      </div>
      <h4 style={{ margin: "0 0 12px 0", fontSize: 14, color: "var(--text-heading)" }}>Segment Profiles</h4>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
        {data.profiles?.map((p) => (
          <div key={p.cluster_id} style={{
            padding: 20, borderRadius: 12, background: "var(--bg-input)", border: "1px solid var(--border-color)",
            borderTop: `4px solid ${clusterColors[p.cluster_id % clusterColors.length]}`,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontWeight: 700, fontSize: 15, color: clusterColors[p.cluster_id % clusterColors.length] }}>{p.label}</span>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{p.percentage}%</span>
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text-heading)", marginBottom: 8 }}>{p.size}</div>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>members</div>
            {p.centroid && (
              <div style={{ marginTop: 12, fontSize: 12, color: "var(--text-secondary)" }}>
                {Object.entries(p.centroid).slice(0, 4).map(([k, v]) => (
                  <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
                    <span>{k}:</span> <span style={{ fontWeight: 600 }}>{v}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {data.feature_importance?.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h4 style={{ margin: "0 0 12px 0", fontSize: 14, color: "var(--text-heading)" }}>Feature Importance</h4>
          {data.feature_importance.map((f) => (
            <div key={f.feature} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
              <span style={{ width: 120, fontSize: 12, color: "var(--text-secondary)" }}>{f.feature}</span>
              <div style={{ flex: 1, height: 8, borderRadius: 4, background: "var(--bg-input)" }}>
                <div style={{ width: `${Math.min(f.importance * 100, 100)}%`, height: "100%", borderRadius: 4, background: "linear-gradient(90deg, var(--accent-purple), var(--accent-blue, #58a6ff))" }} />
              </div>
              <span style={{ fontSize: 12, color: "var(--text-muted)", minWidth: 40 }}>{(f.importance * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function KnowledgeGraphResult({ data }) {
  return (
    <div className="dp-card" style={{ padding: 24 }}>
      <h3 style={{ margin: "0 0 16px 0", fontSize: 16, color: "var(--text-heading)" }}>🕸️ Knowledge Graph</h3>
      {data.summary && (
        <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
          <MetricCard label="Tables" value={data.summary.table_count || 0} color="var(--accent-purple)" />
          <MetricCard label="Columns" value={data.summary.column_count || 0} />
          <MetricCard label="Relationships" value={data.summary.edge_count || 0} color="var(--accent-blue, #58a6ff)" />
        </div>
      )}
      {data.tables?.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: 12, marginBottom: 20 }}>
          {data.tables.map((t, i) => (
            <div key={i} style={{ padding: 16, borderRadius: 8, background: "var(--bg-input)", border: "1px solid var(--border-color)" }}>
              <div style={{ fontWeight: 600, fontSize: 14, color: "var(--accent-purple)", marginBottom: 4 }}>{t.name || t}</div>
              {t.column_count && <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{t.column_count} columns</div>}
            </div>
          ))}
        </div>
      )}
      {data.relationships?.length > 0 && (
        <>
          <h4 style={{ margin: "0 0 12px 0", fontSize: 14, color: "var(--text-heading)" }}>Relationships</h4>
          <div style={{ overflowX: "auto", borderRadius: 8, border: "1px solid var(--border-light)" }}>
            <table style={{ width: "100%", margin: 0 }}>
              <thead><tr><th>From</th><th>To</th><th>Type</th><th>Confidence</th></tr></thead>
              <tbody>
                {data.relationships.map((r, i) => (
                  <tr key={i}>
                    <td>{r.source || r.from}</td>
                    <td>{r.target || r.to}</td>
                    <td><span className="dp-badge" style={{ fontSize: 10 }}>{r.type || r.relationship_type}</span></td>
                    <td>{r.confidence ? `${Math.round(r.confidence * 100)}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function SemanticResult({ data }) {
  return (
    <div>
      <div className="dp-card" style={{ padding: 24, marginBottom: 16 }}>
        <h3 style={{ margin: "0 0 16px 0", fontSize: 16, color: "var(--text-heading)" }}>📊 Semantic Metrics</h3>
        {data.metrics?.length > 0 ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
            {data.metrics.map((m, i) => (
              <div key={i} style={{ padding: 16, borderRadius: 8, background: "var(--bg-input)", border: "1px solid var(--border-color)", borderLeft: "4px solid var(--accent-purple)" }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: "var(--text-heading)" }}>{m.name}</div>
                <div style={{ fontSize: 12, color: "var(--accent-purple)", fontFamily: "monospace", margin: "4px 0" }}>
                  {m.aggregation?.toUpperCase()}({m.column_name})
                </div>
                {m.synonyms?.length > 0 && (
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                    Synonyms: {m.synonyms.join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No metrics discovered yet. Process a dataset to auto-populate.</p>}
      </div>
      <div className="dp-card" style={{ padding: 24 }}>
        <h3 style={{ margin: "0 0 16px 0", fontSize: 16, color: "var(--text-heading)" }}>🏷️ Semantic Dimensions</h3>
        {data.dimensions?.length > 0 ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: 12 }}>
            {data.dimensions.map((d, i) => (
              <div key={i} style={{ padding: 16, borderRadius: 8, background: "var(--bg-input)", border: "1px solid var(--border-color)", borderLeft: "4px solid var(--accent-blue, #58a6ff)" }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: "var(--text-heading)" }}>{d.name}</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                  {d.table_name}.{d.column_name}
                  {d.distinct_count && ` · ${d.distinct_count} unique values`}
                </div>
              </div>
            ))}
          </div>
        ) : <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No dimensions discovered yet.</p>}
      </div>
    </div>
  );
}

function MetricCard({ label, value, color }) {
  return (
    <div style={{
      padding: "12px 20px", borderRadius: 10, background: "var(--bg-input)",
      border: "1px solid var(--border-color)", minWidth: 100,
    }}>
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.5px" }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color || "var(--text-heading)" }}>{value ?? "—"}</div>
    </div>
  );
}

function priorityColor(p) {
  if (p >= 4) return "var(--accent-purple)";
  if (p >= 3) return "var(--accent-blue, #58a6ff)";
  if (p >= 2) return "var(--accent-orange)";
  return "var(--border-color)";
}

function typeBackground(t) {
  const map = {
    query_suggestion: "rgba(138,43,226,0.1)",
    ml_suggestion: "rgba(88,166,255,0.1)",
    data_quality: "rgba(243,156,18,0.1)",
    analysis_hint: "rgba(46,204,113,0.1)",
  };
  return map[t] || "var(--bg-input)";
}

function typeColor(t) {
  const map = {
    query_suggestion: "var(--accent-purple)",
    ml_suggestion: "var(--accent-blue, #58a6ff)",
    data_quality: "var(--accent-orange)",
    analysis_hint: "var(--accent-green)",
  };
  return map[t] || "var(--text-secondary)";
}
