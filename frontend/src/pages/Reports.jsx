import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import api from "../api/axios";
import { getExecutiveSummary, generatePdfReport, generateExcelReport, listReports } from "../api/reports";
import { getWorkspaces } from "../api/workspace";

export default function Reports() {
  const location = useLocation();
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getWorkspaces().then((res) => {
      setWorkspaces(res.data);
      if (res.data.length > 0) {
        const passedWsId = location.state?.workspaceId;
        if (passedWsId && res.data.some(w => w.id === passedWsId)) {
          setActiveWorkspaceId(passedWsId);
        } else {
          setActiveWorkspaceId(res.data[0].id);
        }
      }
    });
  }, [location.state?.workspaceId]);

  const fetchAll = async (workspaceId) => {
    setLoading(true);
    setError("");
    setSummary(null);
    setReports([]);

    try {
      // Fetch both concurrently but handle failures independently
      const summaryPromise = getExecutiveSummary(workspaceId).catch(err => {
        console.warn("Summary failed:", err.response?.data?.detail);
        return { data: null, error: err.response?.data?.detail };
      });
      const reportsPromise = listReports(workspaceId).catch(err => {
        console.error("Reports failed:", err.response?.data?.detail);
        return { data: [] };
      });

      const [summaryRes, reportsRes] = await Promise.all([summaryPromise, reportsPromise]);
      
      if (summaryRes.error) {
        setError(summaryRes.error);
      }
      
      setSummary(summaryRes.data);
      setReports(reportsRes.data || []);
    } catch (err) {
      setError("An unexpected error occurred while loading reports.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeWorkspaceId) fetchAll(activeWorkspaceId);
  }, [activeWorkspaceId]);

  const handleGenerate = async (format) => {
    setGenerating(format);
    setError("");
    try {
      if (format === "pdf") await generatePdfReport(activeWorkspaceId);
      else await generateExcelReport(activeWorkspaceId);
      fetchAll(activeWorkspaceId);
    } catch (err) {
      setError(`Failed to generate ${format.toUpperCase()} report`);
    } finally {
      setGenerating("");
    }
  };

  const handleDownload = async (report) => {
    try {
      const res = await api.get(`/reports/download/${report.id}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", report.file_name);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      setError("Download failed");
    }
  };

  return (
    <div className="app-container">
      <Sidebar />
      <div className="dp-main">
        <Navbar title="Executive Reports" subtitle="AI-generated summaries and structured report downloads" />
        <div className="dp-content">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
            <h2 style={{ margin: 0 }}>Reporting Center</h2>
            <select value={activeWorkspaceId || ""} onChange={(e) => setActiveWorkspaceId(Number(e.target.value))}
              style={{ background: "var(--bg-card)", color: "var(--text-primary)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)", padding: "8px 16px", flex: "1 1 auto", maxWidth: 300 }}>
              {workspaces.map((ws) => <option key={ws.id} value={ws.id}>{ws.name}</option>)}
            </select>
          </div>

          {error && (
            <div style={{ padding: "12px 16px", background: "rgba(231, 76, 60, 0.1)", color: "var(--accent-red)", borderRadius: "var(--radius-sm)", marginBottom: 24 }}>
              {error}
            </div>
          )}
          
          {loading && (
            <div style={{ display: "flex", justifyContent: "center", padding: 40, color: "var(--text-muted)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="spin" style={{ marginRight: 12 }}><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
              Loading reports...
            </div>
          )}

          {summary && (
            <div className="dp-card animate-fade-in" style={{ marginBottom: 32, borderTop: "4px solid var(--accent-blue)" }}>
              <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 12, color: "var(--text-heading)" }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--accent-blue)" }}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                AI Executive Summary
              </h3>
              <p style={{ color: "var(--text-primary)", lineHeight: 1.6 }}>{summary.narrative}</p>
              
              {summary.recommendations?.length > 0 && (
                <div style={{ marginTop: 24, padding: 20, background: "var(--bg-hover)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-light)" }}>
                  <h4 style={{ margin: "0 0 16px 0", color: "var(--accent-orange)", display: "flex", alignItems: "center", gap: 8 }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                    Strategic Recommendations
                  </h4>
                  <ul style={{ margin: 0, paddingLeft: 20, color: "var(--text-secondary)" }}>
                    {summary.recommendations.map((r, i) => <li key={i} style={{ marginBottom: 8 }}>{r}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div className="dp-card animate-fade-in" style={{ animationDelay: "0.1s" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
              <h3 style={{ margin: 0, color: "var(--text-heading)" }}>Report History</h3>
              <div style={{ display: "flex", gap: 12 }}>
                <button onClick={() => handleGenerate("pdf")} disabled={generating === "pdf"}>
                  {generating === "pdf" ? "Generating..." : "Generate PDF"}
                </button>
                <button className="secondary" onClick={() => handleGenerate("xlsx")} disabled={generating === "xlsx"}>
                  {generating === "xlsx" ? "Generating..." : "Generate Excel"}
                </button>
              </div>
            </div>

            {reports.length === 0 ? (
              <div style={{ padding: "40px 0", textAlign: "center", color: "var(--text-secondary)" }}>
                No reports generated yet. Click generate above to create one.
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>File Name</th>
                      <th>Type</th>
                      <th>Format</th>
                      <th>Created</th>
                      <th style={{ textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reports.map((r) => (
                      <tr key={r.id}>
                        <td style={{ color: "var(--text-heading)", fontWeight: 500 }}>{r.file_name}</td>
                        <td><span className="dp-badge" style={{ background: "rgba(124, 108, 246, 0.1)", color: "var(--accent-purple)", border: "1px solid rgba(124, 108, 246, 0.2)" }}>{r.report_type}</span></td>
                        <td>{r.file_format.toUpperCase()}</td>
                        <td style={{ color: "var(--text-secondary)" }}>{new Date(r.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</td>
                        <td style={{ textAlign: "right" }}>
                          <button style={{ padding: "6px 12px", fontSize: 13 }} onClick={() => handleDownload(r)}>Download</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}