// import { useAuth } from "../context/AuthContext";
// import { useNavigate } from "react-router-dom";

// export default function Navbar() {
//   const { logout } = useAuth();
//   const navigate = useNavigate();

//   const handleLogout = () => {
//     logout();
//     navigate("/login");
//   };

//   return (
//     <nav style={{ display: "flex", justifyContent: "space-between", padding: "12px 24px", borderBottom: "1px solid #ddd" }}>
//       <strong>DataPilot AI</strong>
//       <button onClick={handleLogout}>Logout</button>
//     </nav>
//   );
// }
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import { Search, Bell, LogOut, Menu } from "lucide-react";
import AIStatusBadge from "./AIStatusBadge";

export default function Navbar({ title = "Analytics Dashboard", subtitle = "Real-time overview of your data" }) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="dp-topbar">
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <button className="secondary mobile-only" style={{ padding: '8px' }} onClick={() => window.dispatchEvent(new Event('toggle-sidebar'))}>
          <Menu size={20} />
        </button>
        <div>
          <h2 style={{ margin: 0, fontSize: "clamp(18px, 4vw, 24px)" }}>{title}</h2>
          <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: "clamp(12px, 3vw, 13px)" }}>{subtitle}</p>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", justifyContent: "flex-end" }}>
        <div className="desktop-only" style={{ display: "flex", alignItems: "center", background: "var(--bg-input)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)", padding: "10px 14px" }}>
          <Search size={16} color="var(--text-secondary)" />
          <input
            placeholder="Search anything..."
            style={{ background: "transparent", border: "none", outline: "none", color: "var(--text-primary)", marginLeft: 8, width: 200, padding: 0 }}
          />
        </div>
        <AIStatusBadge />
        <button className="secondary" style={{ padding: "10px" }} title="Notifications">
          <Bell size={18} color="var(--text-secondary)" />
        </button>
        <button
          className="secondary"
          onClick={() => { logout(); navigate("/login"); }}
          title="Logout"
        >
          <LogOut size={16} /> <span className="desktop-only">Logout</span>
        </button>
      </div>
    </div>
  );
}