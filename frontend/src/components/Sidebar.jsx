import { useState, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { LayoutDashboard, Upload as UploadIcon, FolderOpen, MessageSquareText, Share2, FileBarChart, Settings, PanelLeftClose, PanelLeftOpen, Sparkles } from "lucide-react";

export default function Sidebar() {
  const [isOpen, setIsOpen] = useState(false);
  const [isMini, setIsMini] = useState(false);

  useEffect(() => {
    const handleToggle = () => setIsOpen(prev => !prev);
    window.addEventListener('toggle-sidebar', handleToggle);
    return () => window.removeEventListener('toggle-sidebar', handleToggle);
  }, []);

  const items = [
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { to: "/workspace", label: "Workspaces", icon: FolderOpen },
    { to: "/upload", label: "Upload Data", icon: UploadIcon },
    { to: "/query", label: "AI Query Assistant", icon: MessageSquareText },
    { to: "/ai-analytics", label: "AI Analytics", icon: Sparkles },
    { to: "/relationships", label: "Relationships", icon: Share2 },
    { to: "/reports", label: "Reports", icon: FileBarChart },
    { to: "/settings", label: "Settings", icon: Settings },
  ];

  return (
    <>
      <div className={`mobile-overlay ${isOpen ? 'open' : ''}`} onClick={() => setIsOpen(false)}></div>
      <aside className={`dp-sidebar ${isOpen ? 'mobile-open' : ''} ${isMini ? 'sidebar-mini' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12h20"/><path d="M12 2v20"/><path d="m4.9 4.9 14.2 14.2"/><path d="m4.9 19.1 14.2-14.2"/></svg>
            </div>
            <span className="sidebar-logo-text">DataPilot AI</span>
          </div>
          <button className="sidebar-toggle-btn desktop-only" onClick={() => setIsMini(!isMini)} title={isMini ? "Expand sidebar" : "Collapse sidebar"}>
            {isMini ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        </div>
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : "")} data-tooltip={label} onClick={() => setIsOpen(false)}>
            <Icon size={18} style={{ flexShrink: 0 }} />
            <span className="sidebar-link-label">{label}</span>
          </NavLink>
        ))}
      </aside>
    </>
  );
}