import { useState, useEffect, useCallback } from "react";
import ReactFlow, { Background, Controls, MarkerType } from "reactflow";
import "reactflow/dist/style.css";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import { discoverRelationships, getRelationshipDiagram } from "../api/relationship";
import { getWorkspaces } from "../api/workspace";

export default function RelationshipDiagram() {
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getWorkspaces().then((res) => {
      setWorkspaces(res.data);
      if (res.data.length > 0) setActiveWorkspaceId(res.data[0].id);
    });
  }, []);

  const fetchDiagram = useCallback(async () => {
    if (!activeWorkspaceId) return;
    setLoading(true);
    setError("");
    try {
      const res = await getRelationshipDiagram(activeWorkspaceId);
      const graphNodes = res.data.nodes.map((n, i) => ({
        id: String(n.id),
        data: { label: `${n.label}${n.primary_key ? ` (PK: ${n.primary_key})` : ""}` },
        position: { x: (i % 3) * 250, y: Math.floor(i / 3) * 150 },
        style: { border: "1px solid #4a90e2", borderRadius: 8, padding: 10 },
      }));
      const graphEdges = res.data.edges.map((e, i) => ({
        id: `e${i}`,
        source: String(e.source),
        target: String(e.target),
        label: `${e.source_column} → ${e.target_column}`,
        animated: e.validated === "valid",
        style: { stroke: e.validated === "valid" ? "#50c878" : e.validated === "invalid" ? "#e74c3c" : "#f5a623" },
        markerEnd: { type: MarkerType.ArrowClosed },
      }));
      setNodes(graphNodes);
      setEdges(graphEdges);
    } catch (err) {
      setError("Failed to load relationship diagram");
    } finally {
      setLoading(false);
    }
  }, [activeWorkspaceId]);

  useEffect(() => {
    fetchDiagram();
  }, [fetchDiagram]);

  const handleDiscover = async () => {
    setLoading(true);
    setError("");
    try {
      await discoverRelationships(activeWorkspaceId);
      fetchDiagram();
    } catch (err) {
      setError(err.response?.data?.detail || "Discovery failed — make sure datasets have been processed via ETL");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <Sidebar />
      <div className="dp-main">
        <Navbar title="Dataset Relationships" subtitle="Explore and validate discovered entity connections" />
        <div className="dp-content">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
            <h2 style={{ margin: 0 }}>Knowledge Graph</h2>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <select value={activeWorkspaceId || ""} onChange={(e) => setActiveWorkspaceId(Number(e.target.value))}
                style={{ background: "var(--bg-card)", color: "var(--text-primary)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)", padding: "8px 16px" }}>
                {workspaces.map((ws) => (
                  <option key={ws.id} value={ws.id}>{ws.name}</option>
                ))}
              </select>
              <button onClick={handleDiscover} disabled={loading} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {loading ? (
                  <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="spin"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg> Analyzing...</>
                ) : (
                  <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg> Re-run Discovery</>
                )}
              </button>
            </div>
          </div>

          {error && (
            <div style={{ padding: "12px 16px", background: "rgba(231, 76, 60, 0.1)", color: "var(--accent-red)", borderRadius: "var(--radius-sm)", marginBottom: 24 }}>
              {error}
            </div>
          )}

          <div className="dp-card animate-fade-in">
            <div style={{ marginBottom: 24, display: "flex", gap: 24, fontSize: 13, color: "var(--text-secondary)" }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}><div style={{ width: 10, height: 10, borderRadius: "50%", background: "#50c878" }}></div> Validated</span>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}><div style={{ width: 10, height: 10, borderRadius: "50%", background: "#f5a623" }}></div> Pending validation</span>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}><div style={{ width: 10, height: 10, borderRadius: "50%", background: "#e74c3c" }}></div> Invalid</span>
            </div>

            <div style={{ height: 600, border: "1px solid var(--border-light)", borderRadius: "var(--radius-md)", overflow: "hidden", background: "var(--bg-hover)" }}>
              {nodes.length > 0 ? (
                <ReactFlow nodes={nodes} edges={edges} fitView>
                  <Background color="var(--border-color)" gap={16} />
                  <Controls style={{ display: 'flex', flexDirection: 'column', gap: 4, background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: 4 }} />
                </ReactFlow>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", height: "100%", color: "var(--text-secondary)", textAlign: "center", padding: 40 }}>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: 16, color: "var(--border-color)" }}><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
                  <p style={{ margin: "0 0 8px 0", fontSize: 16, color: "var(--text-primary)" }}>No relationships found yet</p>
                  <p style={{ margin: 0, maxWidth: 400 }}>Make sure at least two datasets have been uploaded and processed via ETL, then click "Re-run Discovery".</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}