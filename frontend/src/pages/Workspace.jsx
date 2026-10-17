import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import { createWorkspace, getWorkspaces, deleteWorkspace } from "../api/workspace";

export default function Workspace() {
  const [workspaces, setWorkspaces] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const fetchWorkspaces = async () => {
    try {
      const res = await getWorkspaces();
      setWorkspaces(res.data);
    } catch (err) {
      setError("Failed to load workspaces");
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await createWorkspace({ name, description });
      setName("");
      setDescription("");
      fetchWorkspaces();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create workspace");
    }
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm("Delete this workspace? This cannot be undone.")) return;
    try {
      await deleteWorkspace(id);
      fetchWorkspaces();
    } catch (err) {
      setError("Failed to delete workspace");
    }
  };

  return (
    <div className="app-container">
      <Sidebar />
      <div className="dp-main">
        <Navbar title="Workspaces" subtitle="Manage your isolated data environments" />
        <div className="dp-content" style={{ maxWidth: 800, margin: "0 auto", width: "100%" }}>
          <div className="dp-card animate-fade-in" style={{ marginBottom: 32 }}>
            <h2 style={{ margin: "0 0 16px 0" }}>Create New Workspace</h2>
            <form onSubmit={handleCreate} style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <input
                placeholder="Workspace name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                style={{ flex: "1 1 200px" }}
              />
              <input
                placeholder="Description (optional)"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{ flex: "2 1 300px" }}
              />
              <button type="submit" style={{ flex: "0 0 auto" }}>Create</button>
            </form>
            {error && <p style={{ color: "var(--accent-red)", marginTop: 12 }}>{error}</p>}
          </div>

          <h3 style={{ marginBottom: 16 }}>Your Workspaces</h3>
          <div style={{ display: "grid", gap: 16 }}>
            {workspaces.map((ws) => (
              <div
                key={ws.id}
                className="dp-card animate-fade-in"
                onClick={() => navigate("/upload", { state: { workspaceId: ws.id } })}
                style={{
                  cursor: "pointer",
                  transition: "transform 0.2s, box-shadow 0.2s",
                  borderLeft: "4px solid var(--accent-purple)",
                }}
                onMouseOver={(e) => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 16px rgba(0,0,0,0.2)"; }}
                onMouseOut={(e) => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "none"; }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <h3 style={{ margin: "0 0 8px 0", fontSize: 18, color: "var(--text-heading)" }}>{ws.name}</h3>
                    <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: 14 }}>{ws.description || "No description provided."}</p>
                  </div>
                  <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                    <button onClick={(e) => handleDelete(e, ws.id)} className="secondary danger" style={{ padding: "6px 12px", fontSize: 13 }}>
                      Delete
                    </button>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--text-muted)" }}><polyline points="9 18 15 12 9 6"></polyline></svg>
                  </div>
                </div>
              </div>
            ))}
            
            {workspaces.length === 0 && (
              <div style={{ padding: "40px 0", textAlign: "center", color: "var(--text-secondary)" }}>
                You don't have any workspaces yet. Create one above to get started.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}