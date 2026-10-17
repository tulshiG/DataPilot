import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, RadialBarChart, RadialBar,
} from "recharts";

// ── Design tokens ──────────────────────────────────────────────────────────
const COLORS = [
  "#7c6cf6", "#4a90e2", "#2ecc71", "#f39c12",
  "#e74c3c", "#1abc9c", "#e67e22", "#9b59b6",
  "#3498db", "#e91e8c", "#00bcd4", "#ff5722",
];

const CHART_DARK = {
  tooltip: { background: "#13141f", border: "1px solid #2a2b3d", borderRadius: 10, color: "#e2e4f0" },
  axis: { fontSize: 11, fill: "#64677a" },
  grid: "#1e1f2e",
};

// ── Small helpers ──────────────────────────────────────────────────────────
const fmt = (v) => {
  if (v == null) return "";
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
};

// ── Chart type badges ──────────────────────────────────────────────────────
const CHART_LABELS = {
  line: { label: "Line", color: "#7c6cf6" },
  bar: { label: "Bar", color: "#4a90e2" },
  donut: { label: "Donut", color: "#f39c12" },
  pie: { label: "Pie", color: "#e67e22" },
  scatter: { label: "Scatter", color: "#e74c3c" },
  histogram: { label: "Histogram", color: "#2ecc71" },
  box: { label: "Box Plot", color: "#1abc9c" },
  heatmap: { label: "Heatmap", color: "#9b59b6" },
  treemap: { label: "Treemap", color: "#3498db" },
};

// ═══════════════════════════════════════════════════════════════════════════
// Individual renderers
// ═══════════════════════════════════════════════════════════════════════════

function LineRenderer({ chart }) {
  const series = chart.series || (chart.x_axis_label ? [chart.x_axis_label] : []);
  const activeKeys = series.length > 0 ? series : Object.keys(chart.data?.[0] || {}).filter(k => k !== "date");
  return (
    <AreaChart data={chart.data} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
      <defs>
        {activeKeys.map((s, i) => (
          <linearGradient key={s} id={`grad_${i}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.35} />
            <stop offset="95%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0} />
          </linearGradient>
        ))}
      </defs>
      <CartesianGrid strokeDasharray="3 3" stroke={CHART_DARK.grid} />
      <XAxis dataKey="date" tick={CHART_DARK.axis} tickFormatter={(v) => v?.slice(0, 10)} />
      <YAxis tick={CHART_DARK.axis} tickFormatter={fmt} />
      <Tooltip contentStyle={CHART_DARK.tooltip} formatter={(v) => fmt(v)} />
      <Legend wrapperStyle={{ fontSize: 11, color: "#8b8d98" }} />
      {activeKeys.map((s, i) => (
        <Area key={s} type="monotone" dataKey={s} stroke={COLORS[i % COLORS.length]}
          fill={`url(#grad_${i})`} strokeWidth={2.5} dot={false} />
      ))}
    </AreaChart>
  );
}

function BarRenderer({ chart }) {
  const isH = chart.orientation === "horizontal";
  const ChartComp = BarChart;
  return (
    <BarChart data={chart.data} layout={isH ? "vertical" : "horizontal"} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
      <CartesianGrid strokeDasharray="3 3" stroke={CHART_DARK.grid} />
      {isH ? (
        <>
          <YAxis type="category" dataKey="category" tick={{ ...CHART_DARK.axis, fontSize: 10 }} width={110}
            tickFormatter={(v) => v?.length > 14 ? v.slice(0, 14) + "…" : v} />
          <XAxis type="number" tick={CHART_DARK.axis} tickFormatter={fmt} />
        </>
      ) : (
        <>
          <XAxis dataKey="category" tick={{ ...CHART_DARK.axis, fontSize: 10 }}
            tickFormatter={(v) => v?.length > 10 ? v.slice(0, 10) + "…" : v} />
          <YAxis tick={CHART_DARK.axis} tickFormatter={fmt} />
        </>
      )}
      <Tooltip contentStyle={CHART_DARK.tooltip} formatter={(v) => fmt(v)} />
      <Bar dataKey="value" radius={isH ? [0, 6, 6, 0] : [6, 6, 0, 0]}>
        {chart.data?.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
      </Bar>
    </BarChart>
  );
}

function PieRenderer({ chart, isDonut = false }) {
  const inner = isDonut ? 56 : 0;
  return (
    <PieChart margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
      <Pie data={chart.data} dataKey="value" nameKey="label"
        innerRadius={inner} outerRadius={90} paddingAngle={isDonut ? 3 : 1}
        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
        labelLine={false}>
        {chart.data?.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
      </Pie>
      <Tooltip contentStyle={CHART_DARK.tooltip} formatter={(v, n) => [fmt(v), n]} />
      <Legend wrapperStyle={{ fontSize: 11, color: "#8b8d98" }} />
    </PieChart>
  );
}

function ScatterRenderer({ chart }) {
  return (
    <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
      <CartesianGrid strokeDasharray="3 3" stroke={CHART_DARK.grid} />
      <XAxis dataKey="x" name={chart.x_axis_label} tick={CHART_DARK.axis} tickFormatter={fmt}
        label={{ value: chart.x_axis_label?.replace(/_/g, " "), position: "insideBottom", offset: -4, fill: "#64677a", fontSize: 11 }} />
      <YAxis dataKey="y" name={chart.y_axis_label} tick={CHART_DARK.axis} tickFormatter={fmt}
        label={{ value: chart.y_axis_label?.replace(/_/g, " "), angle: -90, position: "insideLeft", fill: "#64677a", fontSize: 11 }} />
      <Tooltip contentStyle={CHART_DARK.tooltip} cursor={{ strokeDasharray: "3 3" }}
        formatter={(v, n) => [fmt(v), n]} />
      <Scatter data={chart.data} fill="#7c6cf6" opacity={0.7} />
    </ScatterChart>
  );
}

function HistogramRenderer({ chart }) {
  return (
    <BarChart data={chart.data} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
      <CartesianGrid strokeDasharray="3 3" stroke={CHART_DARK.grid} />
      <XAxis dataKey="range" tick={{ ...CHART_DARK.axis, fontSize: 9 }}
        tickFormatter={(v) => v?.split(" ")[0]} />
      <YAxis tick={CHART_DARK.axis} tickFormatter={fmt} />
      <Tooltip contentStyle={CHART_DARK.tooltip} />
      <Bar dataKey="count" radius={[4, 4, 0, 0]} fill="#4a90e2" />
    </BarChart>
  );
}

// ── Box Plot (custom — recharts has no native box plot) ────────────────────
function BoxPlotRenderer({ chart }) {
  if (!chart.data?.length) return <Empty msg="No data" />;
  const groups = chart.data.slice(0, 6);
  const allVals = groups.flatMap(d => [d.min, d.max]).filter(Boolean);
  const minY = Math.min(...allVals);
  const maxY = Math.max(...allVals);
  const range = maxY - minY || 1;

  const toPercent = (v) => ((v - minY) / range) * 100;

  return (
    <div style={{ display: "flex", gap: 16, alignItems: "flex-end", height: "100%", padding: "8px 0" }}>
      {groups.map((d, i) => {
        const boxBottom = toPercent(d.q1);
        const boxHeight = toPercent(d.q3) - boxBottom;
        const medPercent = toPercent(d.median);
        return (
          <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, height: "100%" }}>
            {/* Box area */}
            <div style={{ flex: 1, width: "100%", position: "relative" }}>
              {/* Whisker top */}
              <div style={{ position: "absolute", left: "50%", bottom: `${toPercent(d.max)}%`, transform: "translateX(-50%)", width: 2, height: `${toPercent(d.max) - toPercent(d.q3)}%`, background: COLORS[i % COLORS.length], opacity: 0.6 }} />
              {/* Box */}
              <div style={{ position: "absolute", left: "15%", width: "70%", bottom: `${boxBottom}%`, height: `${Math.max(boxHeight, 3)}%`, background: `${COLORS[i % COLORS.length]}40`, border: `2px solid ${COLORS[i % COLORS.length]}`, borderRadius: 4 }}>
                {/* Median line */}
                <div style={{ position: "absolute", left: 0, right: 0, bottom: `${toPercent(d.median) - boxBottom}%`, height: 2, background: COLORS[i % COLORS.length] }} />
              </div>
              {/* Whisker bottom */}
              <div style={{ position: "absolute", left: "50%", bottom: `${toPercent(d.q1)}%`, transform: "translateX(-50%)", width: 2, height: `${toPercent(d.q1) - toPercent(d.min)}%`, background: COLORS[i % COLORS.length], opacity: 0.6 }} />
            </div>
            <span style={{ fontSize: 10, color: "#64677a", textAlign: "center", maxWidth: "100%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {d.group}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Heatmap ─────────────────────────────────────────────────────────────────
function HeatmapRenderer({ chart }) {
  const { columns = [], data = [] } = chart;
  const n = columns.length;
  if (!n) return <Empty msg="Not enough numeric columns" />;

  const getColor = (val) => {
    // -1 → red, 0 → dark, +1 → purple
    if (val > 0) return `rgba(124, 108, 246, ${Math.min(val, 1)})`;
    return `rgba(231, 76, 60, ${Math.min(Math.abs(val), 1)})`;
  };

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 11 }}>
        <thead>
          <tr>
            <th style={{ width: 80 }} />
            {columns.map(c => (
              <th key={c} style={{ padding: "4px 2px", color: "#64677a", fontWeight: 500, transform: "rotate(-35deg)", whiteSpace: "nowrap" }}>
                {c.replace(/_/g, " ").slice(0, 10)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {columns.map(row => (
            <tr key={row}>
              <td style={{ padding: "2px 8px", color: "#64677a", fontSize: 10, whiteSpace: "nowrap" }}>
                {row.replace(/_/g, " ").slice(0, 12)}
              </td>
              {columns.map(col => {
                const cell = data.find(d => d.x === col && d.y === row);
                const v = cell?.value ?? 0;
                const isIdentity = row === col;
                return (
                  <td key={col} title={`${row} ↔ ${col}: ${v}`}
                    style={{
                      width: 44, height: 36, textAlign: "center",
                      background: isIdentity ? "#2a2b3d" : getColor(v),
                      borderRadius: 4, border: "2px solid #0a0b10",
                      color: Math.abs(v) > 0.5 ? "#fff" : "#8b8d98",
                      fontWeight: 600, fontSize: 10, cursor: "default",
                    }}>
                    {isIdentity ? "—" : v.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Treemap (bar with special styling) ────────────────────────────────────
function TreemapRenderer({ chart }) {
  const total = chart.data?.reduce((s, d) => s + (d.value || 0), 0) || 1;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, height: "100%", alignContent: "flex-start" }}>
      {chart.data?.slice(0, 12).map((d, i) => {
        const pct = (d.value / total) * 100;
        return (
          <div key={i} title={`${d.category}: ${fmt(d.value)}`}
            style={{
              flex: `${pct} 0 ${Math.max(pct, 8)}%`,
              minWidth: 60, minHeight: 40, maxWidth: "48%",
              background: `${COLORS[i % COLORS.length]}22`,
              border: `2px solid ${COLORS[i % COLORS.length]}`,
              borderRadius: 8, display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", padding: 8,
              cursor: "default",
            }}>
            <span style={{ fontSize: 10, color: "#8b8d98", textAlign: "center", lineHeight: 1.2 }}>
              {d.category?.slice(0, 14)}
            </span>
            <span style={{ fontSize: 13, fontWeight: 700, color: COLORS[i % COLORS.length] }}>
              {fmt(d.value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function Empty({ msg }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#64677a", fontSize: 13 }}>
      {msg || "No data available"}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Main ChartCard component
// ═══════════════════════════════════════════════════════════════════════════
export default function ChartCard({ chart, fullWidth = false }) {
  const { chart_type, data } = chart;

  const hasData = Array.isArray(data) && data.length > 0;

  const badge = CHART_LABELS[chart_type];

  const renderChart = () => {
    if (!hasData && !["heatmap", "box"].includes(chart_type)) return <Empty />;
    switch (chart_type) {
      case "line":   return <LineRenderer chart={chart} />;
      case "bar":    return <BarRenderer chart={chart} />;
      case "donut":  return <PieRenderer chart={chart} isDonut />;
      case "pie":    return <PieRenderer chart={chart} />;
      case "scatter": return <ScatterRenderer chart={chart} />;
      case "histogram": return <HistogramRenderer chart={chart} />;
      case "box":    return <BoxPlotRenderer chart={chart} />;
      case "heatmap": return <HeatmapRenderer chart={chart} />;
      case "treemap": return <TreemapRenderer chart={chart} />;
      default: return <Empty msg={`Unknown chart type: ${chart_type}`} />;
    }
  };

  // Scatter and heatmap get correlation insight
  const insight = chart.correlation != null
    ? `Correlation: ${chart.correlation > 0 ? "+" : ""}${chart.correlation}`
    : null;

  return (
    <div className={`dp-card chart-card ${fullWidth ? "chart-card-full" : ""}`}
      style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "var(--text-heading)", lineHeight: 1.3 }}>
            {chart.title || chart.dataset_name}
          </h4>
          {insight && (
            <span style={{ fontSize: 11, color: "#8b8d98", marginTop: 3, display: "block" }}>
              {insight}
            </span>
          )}
        </div>
        {badge && (
          <span style={{
            flexShrink: 0, marginLeft: 10, padding: "3px 9px",
            borderRadius: 20, fontSize: 10, fontWeight: 700,
            letterSpacing: 0.5, textTransform: "uppercase",
            background: `${badge.color}20`, color: badge.color,
            border: `1px solid ${badge.color}40`,
          }}>
            {badge.label}
          </span>
        )}
      </div>

      {/* Chart body */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {["box", "heatmap", "treemap"].includes(chart_type) ? (
          <div style={{ height: 240 }}>{renderChart()}</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            {renderChart()}
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}