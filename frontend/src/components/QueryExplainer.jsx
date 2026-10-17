/**
 * QueryExplainer — Renders the step-by-step explanation of how a query was processed.
 * Shows intent, table resolution, column mapping, filters, corrections, and confidence.
 */
export default function QueryExplainer({ explanation }) {
  if (!explanation) return null;

  const { engine, steps, confidence, summary } = explanation;

  return (
    <div style={{
      borderRadius: 12, overflow: "hidden",
      border: "1px solid var(--border-color, #2a2a4a)",
      background: "var(--bg-card, #12122a)",
      marginTop: 16,
    }}>
      {/* Header */}
      <div style={{
        padding: "16px 20px",
        background: "linear-gradient(135deg, rgba(138,43,226,0.1), rgba(88,166,255,0.1))",
        borderBottom: "1px solid var(--border-light, #1e1e3a)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 20 }}>{engine?.icon || "🔍"}</span>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: "var(--text-heading)" }}>
              {engine?.name || "Query Engine"}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
              {engine?.description}
            </div>
          </div>
        </div>

        {confidence && (
          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "6px 14px", borderRadius: 20,
            background: "var(--bg-input)", border: "1px solid var(--border-color)",
          }}>
            <span style={{ fontSize: 16 }}>{confidence.icon}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-heading)" }}>
              {Math.round(confidence.score * 100)}%
            </span>
          </div>
        )}
      </div>

      {/* Steps */}
      <div style={{ padding: "16px 20px" }}>
        {steps?.map((step, i) => (
          <div
            key={i}
            style={{
              display: "flex", gap: 16, padding: "12px 0",
              borderBottom: i < steps.length - 1 ? "1px solid var(--border-light, #1e1e3a)" : "none",
            }}
          >
            <div style={{
              width: 28, height: 28, borderRadius: "50%",
              background: "linear-gradient(135deg, var(--accent-purple, #8a2be2), var(--accent-blue, #58a6ff))",
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0, fontSize: 12, fontWeight: 700, color: "#fff",
            }}>
              {step.step}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-heading)" }}>
                {step.name}
              </div>
              <div style={{ fontSize: 12, color: "var(--accent-purple, #8a2be2)", marginTop: 2, fontFamily: "monospace" }}>
                {step.result}
              </div>
              {step.detail && (
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4, lineHeight: 1.4 }}>
                  {step.detail}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Summary */}
      {summary && (
        <div style={{
          padding: "12px 20px",
          borderTop: "1px solid var(--border-light, #1e1e3a)",
          fontSize: 12, color: "var(--text-muted)", fontStyle: "italic",
        }}>
          {summary}
        </div>
      )}
    </div>
  );
}
