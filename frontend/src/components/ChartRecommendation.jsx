/**
 * ChartRecommendation — Shows the AI-recommended chart type with alternatives. 
 */
export default function ChartRecommendation({ recommendation }) {
  if (!recommendation) return null;

  const { recommended, alternatives, reasoning, encodings } = recommendation;

  const chartIcons = {
    bar: "📊", horizontal_bar: "📊", line: "📈", area: "📈",
    pie: "🥧", donut: "🍩", scatter: "🔵", heatmap: "🗺️",
    histogram: "📊", kpi_card: "🎯", table: "📋",
    stacked_bar: "📊", grouped_bar: "📊",
  };

  return (
    <div style={{
      padding: 16, borderRadius: 12,
      border: "1px solid var(--border-color, #2a2a4a)",
      background: "var(--bg-card, #12122a)",
      marginTop: 16,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-purple)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
          <polyline points="7.5 4.21 12 6.81 16.5 4.21"/><polyline points="7.5 19.79 7.5 14.6 3 12"/><polyline points="21 12 16.5 14.6 16.5 19.79"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-heading)" }}>
          Chart Recommendation
        </span>
      </div>

      {/* Primary recommendation */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "12px 16px", borderRadius: 8,
        background: "linear-gradient(135deg, rgba(138,43,226,0.08), rgba(88,166,255,0.08))",
        border: "1px solid rgba(138,43,226,0.2)",
        marginBottom: 12,
      }}>
        <span style={{ fontSize: 24 }}>{chartIcons[recommended?.type] || "📊"}</span>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, color: "var(--text-heading)" }}>
            {recommended?.name || recommended?.type}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
            {recommended?.description}
          </div>
        </div>
        <span style={{
          marginLeft: "auto",
          padding: "4px 10px", borderRadius: 12,
          background: "var(--accent-purple, #8a2be2)", color: "#fff",
          fontSize: 11, fontWeight: 600,
        }}>
          {recommended?.score}%
        </span>
      </div>

      {/* Alternatives */}
      {alternatives?.length > 0 && (
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
          {alternatives.map((alt, i) => (
            <span key={i} style={{
              padding: "4px 12px", borderRadius: 16,
              background: "var(--bg-input)", border: "1px solid var(--border-color)",
              fontSize: 12, color: "var(--text-secondary)",
              display: "flex", alignItems: "center", gap: 4,
            }}>
              {chartIcons[alt.type] || "📊"} {alt.name || alt.type}
            </span>
          ))}
        </div>
      )}

      {/* Encodings */}
      {encodings && Object.keys(encodings).length > 0 && (
        <div style={{
          display: "flex", gap: 16, fontSize: 12,
          color: "var(--text-muted)", padding: "8px 0",
          borderTop: "1px solid var(--border-light, #1e1e3a)",
        }}>
          {encodings.x && <span>X: <code style={{ color: "var(--accent-blue)" }}>{encodings.x}</code></span>}
          {encodings.y && <span>Y: <code style={{ color: "var(--accent-green)" }}>{encodings.y}</code></span>}
          {encodings.color && <span>Color: <code style={{ color: "var(--accent-orange)" }}>{encodings.color}</code></span>}
        </div>
      )}

      {/* Reasoning */}
      {reasoning && (
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8, fontStyle: "italic" }}>
          {reasoning}
        </div>
      )}
    </div>
  );
}
