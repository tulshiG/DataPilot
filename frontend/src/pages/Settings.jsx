import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import { getAIStatus } from "../api/ai";

export default function Settings() {
  const [aiStatus, setAiStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getAIStatus()
      .then(res => setAiStatus(res.data))
      .catch(() => setAiStatus(null))
      .finally(() => setLoading(false));
  }, []);

  const refresh = () => {
    setLoading(true);
    getAIStatus()
      .then(res => setAiStatus(res.data))
      .catch(() => setAiStatus(null))
      .finally(() => setLoading(false));
  };

  const statusDot = (ok) => (
    <span style={{
      display: "inline-block", width: 8, height: 8, borderRadius: "50%",
      background: ok ? "#2ecc71" : "#e74c3c",
      boxShadow: ok ? "0 0 6px #2ecc71" : "0 0 6px #e74c3c",
    }} />
  );

  return (
    <div className="app-container">
      <Sidebar />
      <div className="dp-main">
        <Navbar title="Settings" subtitle="Manage your account and platform preferences" />
        <div className="dp-content" style={{ maxWidth: 860, margin: "0 auto", width: "100%", padding: 24 }}>

          {/* ── AI Engine Status ─────────────────────────────────── */}
          <div className="dp-card animate-fade-in" style={{ padding: 28, marginBottom: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{
                  width: 36, height: 36, borderRadius: 10,
                  background: "linear-gradient(135deg, #8a2be2, #58a6ff)",
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
                }}>🧠</span>
                <div>
                  <h3 style={{ margin: 0, fontSize: 17, color: "var(--text-heading)" }}>AI Engine Status</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "var(--text-muted)" }}>Real-time health of all AI/ML components</p>
                </div>
              </div>
              <button onClick={refresh} disabled={loading} className="secondary" style={{ fontSize: 12, padding: "6px 16px" }}>
                {loading ? "Checking…" : "↻ Refresh"}
              </button>
            </div>

            {aiStatus ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                {/* Ollama LLM */}
                <div style={{
                  padding: 20, borderRadius: 10, background: "var(--bg-input)",
                  border: "1px solid var(--border-color)",
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    {statusDot(aiStatus.ollama?.available)}
                    <span style={{ fontWeight: 600, fontSize: 14, color: "var(--text-heading)" }}>Ollama LLM</span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.8 }}>
                    <div>Status: <span style={{ color: aiStatus.ollama?.available ? "#2ecc71" : "#e74c3c", fontWeight: 600 }}>
                      {aiStatus.ollama?.available ? "Connected" : "Unavailable"}
                    </span></div>
                    {aiStatus.ollama?.model && <div>Model: <span style={{ color: "var(--accent-purple)" }}>{aiStatus.ollama.model}</span></div>}
                    {aiStatus.ollama?.url && <div>URL: <span style={{ fontFamily: "monospace", fontSize: 11 }}>{aiStatus.ollama.url}</span></div>}
                  </div>
                </div>

                {/* Embeddings */}
                <div style={{
                  padding: 20, borderRadius: 10, background: "var(--bg-input)",
                  border: "1px solid var(--border-color)",
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    {statusDot(aiStatus.embeddings?.available)}
                    <span style={{ fontWeight: 600, fontSize: 14, color: "var(--text-heading)" }}>Embedding Model</span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.8 }}>
                    <div>Status: <span style={{ color: aiStatus.embeddings?.available ? "#2ecc71" : "#e74c3c", fontWeight: 600 }}>
                      {aiStatus.embeddings?.available ? "Loaded" : "Not loaded"}
                    </span></div>
                    {aiStatus.embeddings?.model && <div>Model: <span style={{ color: "var(--accent-purple)" }}>{aiStatus.embeddings.model}</span></div>}
                    {aiStatus.embeddings?.dimension && <div>Dimensions: {aiStatus.embeddings.dimension}</div>}
                  </div>
                </div>

                {/* FAISS Index */}
                <div style={{
                  padding: 20, borderRadius: 10, background: "var(--bg-input)",
                  border: "1px solid var(--border-color)",
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    {statusDot(aiStatus.faiss?.available)}
                    <span style={{ fontWeight: 600, fontSize: 14, color: "var(--text-heading)" }}>FAISS Vector Store</span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.8 }}>
                    <div>Status: <span style={{ color: aiStatus.faiss?.available ? "#2ecc71" : "#e74c3c", fontWeight: 600 }}>
                      {aiStatus.faiss?.available ? "Ready" : "No index"}
                    </span></div>
                    {aiStatus.faiss?.total_vectors != null && <div>Vectors: {aiStatus.faiss.total_vectors.toLocaleString()}</div>}
                  </div>
                </div>

                {/* Overall */}
                <div style={{
                  padding: 20, borderRadius: 10,
                  background: aiStatus.overall === "operational"
                    ? "rgba(46,204,113,0.08)" : "rgba(243,156,18,0.08)",
                  border: `1px solid ${aiStatus.overall === "operational" ? "rgba(46,204,113,0.3)" : "rgba(243,156,18,0.3)"}`,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    {statusDot(aiStatus.overall === "operational")}
                    <span style={{ fontWeight: 600, fontSize: 14, color: "var(--text-heading)" }}>Overall</span>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: aiStatus.overall === "operational" ? "#2ecc71" : "#f39c12" }}>
                    {aiStatus.overall === "operational" ? "✓ All Systems Operational" : "⚠ Partial — Keyword fallback active"}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>
                    The system works without Ollama using keyword-based NLP.
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: 32, color: "var(--text-muted)" }}>
                {loading ? "Checking AI engine status…" : "Could not reach AI status endpoint. Is the backend running?"}
              </div>
            )}
          </div>

          {/* ── Platform Info ────────────────────────────────────── */}
          <div className="dp-card animate-fade-in" style={{ padding: 28, marginBottom: 24 }}>
            <h3 style={{ margin: "0 0 20px 0", fontSize: 16, color: "var(--text-heading)", borderBottom: "1px solid var(--border-light)", paddingBottom: 14 }}>
              Platform Information
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[
                ["Platform", "DataPilot AI v2"],
                ["Architecture", "Self-hosted · Zero external APIs"],
                ["NLP Engine", "LLM (Ollama) + Keyword fallback"],
                ["ML Engine", "Forecasting · Anomaly · Segmentation"],
                ["Vector DB", "FAISS (local)"],
                ["SQL Safety", "sqlglot validation + LIMIT enforcement"],
                ["Graph Engine", "NetworkX knowledge graph"],
                ["Explainability", "Step-by-step query reasoning"],
              ].map(([k, v]) => (
                <div key={k} style={{ padding: "10px 14px", borderRadius: 8, background: "var(--bg-input)", border: "1px solid var(--border-color)" }}>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 2 }}>{k}</div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-heading)" }}>{v}</div>
                </div>
              ))}
            </div>
          </div>

          {/* ── Dependencies ─────────────────────────────────────── */}
          <div className="dp-card animate-fade-in" style={{ padding: 28 }}>
            <h3 style={{ margin: "0 0 20px 0", fontSize: 16, color: "var(--text-heading)", borderBottom: "1px solid var(--border-light)", paddingBottom: 14 }}>
              Setup Checklist
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { label: "PostgreSQL database", done: true, detail: "Core data storage" },
                { label: "Python dependencies installed", done: true, detail: "pip install -r requirements.txt" },
                { label: "AI metadata tables migrated", done: true, detail: "migrations/002_ai_metadata_tables.sql" },
                { label: "Semantic layer tables migrated", done: true, detail: "migrations/003_semantic_layer_tables.sql" },
                { label: "Ollama installed (optional)", done: aiStatus?.ollama?.available, detail: "ollama pull mistral" },
                { label: "Datasets processed", done: true, detail: "Upload → auto-processed with AI metadata" },
              ].map((item, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
                  borderRadius: 6, background: "var(--bg-input)", border: "1px solid var(--border-color)",
                }}>
                  <span style={{ fontSize: 14, minWidth: 20, textAlign: "center" }}>
                    {item.done ? "✅" : "⬜"}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-heading)" }}>{item.label}</div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{item.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
