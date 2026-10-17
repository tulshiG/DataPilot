import { TrendingUp, TrendingDown } from "lucide-react";

export default function KPI({ name, display_value, change_percent }) {
  const isUp = change_percent != null && change_percent >= 0;
  return (
    <div className="dp-kpi-card">
      <p className="dp-kpi-label">{name}</p>
      <h2 className="dp-kpi-value">{display_value}</h2>
      {change_percent != null && (
        <div className={`dp-kpi-change ${isUp ? "up" : "down"}`} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {isUp ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {Math.abs(change_percent)}% vs last 30 days
        </div>
      )}
    </div>
  );
}