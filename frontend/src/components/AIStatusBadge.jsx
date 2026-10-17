import { useState, useEffect } from "react";
import { getAIStatus } from "../api/ai";

export default function AIStatusBadge() {
  const [status, setStatus] = useState(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    getAIStatus()
      .then((res) => setStatus(res.data))
      .catch(() => setStatus({ overall: "unavailable" }));
  }, []);

  if (!status) return null;

  const isOperational = status.overall === "operational";
  const isDegraded = status.overall === "degraded";

  const dotColor = isOperational
    ? "var(--accent-green, #2ecc71)"
    : isDegraded
    ? "var(--accent-orange, #f39c12)"
    : "var(--accent-red, #e74c3c)";

  const label = isOperational
    ? "AI Active"
    : isDegraded
    ? "Keyword Mode"
    : "Offline";

  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "6px 14px", borderRadius: 20,
          background: "var(--bg-input, #1a1a2e)", border: "1px solid var(--border-color, #2a2a4a)",
          cursor: "pointer", fontSize: 12, fontWeight: 500,
          color: "var(--text-secondary, #a0a0c0)", transition: "all 0.2s",
        }}
        onMouseOver={(e) => e.currentTarget.style.borderColor = dotColor}
        onMouseOut={(e) => e.currentTarget.style.borderColor = "var(--border-color, #2a2a4a)"}
      >
        <span
          style={{
            width: 8, height: 8, borderRadius: "50%",
            background: dotColor,
            boxShadow: `0 0 8px ${dotColor}`,
            animation: isOperational ? "pulse 2s infinite" : "none",
          }}
        />
        {label}
      </button>

      {expanded && (
        <div
          style={{
            position: "absolute", top: "calc(100% + 8px)", right: 0,
            background: "var(--bg-card, #12122a)", border: "1px solid var(--border-color, #2a2a4a)",
            borderRadius: 12, padding: 20, minWidth: 280,
            boxShadow: "0 12px 40px rgba(0,0,0,0.4)",
            zIndex: 1000, fontSize: 13,
          }}
        >
          <h4 style={{ margin: "0 0 16px 0", fontSize: 14, color: "var(--text-heading, #fff)" }}>
            AI Engine Status
          </h4>

          <StatusRow
            label="LLM (Ollama)"
            ok={status.ollama?.available}
            detail={status.ollama?.available ? status.config?.ollama_model : "Not connected"}
          />
          <StatusRow
            label="Embeddings"
            ok={status.embeddings?.available}
            detail={status.embeddings?.model || "—"}
          />
          <StatusRow
            label="Fallback"
            ok={true}
            detail={status.fallback_active ? "Active (keyword mode)" : "Standby"}
            color={status.fallback_active ? "var(--accent-orange)" : "var(--accent-green)"}
          />

          {status.ollama && !status.ollama.available && (
            <p style={{
              margin: "16px 0 0 0", padding: 12, borderRadius: 8,
              background: "rgba(243, 156, 18, 0.1)", fontSize: 12,
              color: "var(--accent-orange)",
              lineHeight: 1.5,
            }}>
              💡 Install Ollama and run <code style={{ background: "rgba(255,255,255,0.1)", padding: "1px 6px", borderRadius: 4 }}>
                ollama pull mistral
              </code> to enable AI-powered queries.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function StatusRow({ label, ok, detail, color }) {
  const statusColor = color || (ok ? "var(--accent-green, #2ecc71)" : "var(--accent-red, #e74c3c)");
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "8px 0", borderBottom: "1px solid var(--border-light, #1e1e3a)",
    }}>
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{detail}</span>
        <span style={{
          width: 6, height: 6, borderRadius: "50%",
          background: statusColor,
        }} />
      </div>
    </div>
  );
}
