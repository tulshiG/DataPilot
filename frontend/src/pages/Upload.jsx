// import { useState, useEffect } from "react";
// import Navbar from "../components/Navbar";
// import Sidebar from "../components/Sidebar";
// import UploadBox from "../components/UploadBox";
// // import { uploadFiles, getDatasets } from "../api/upload";
// import { getWorkspaces } from "../api/workspace";
// import api from "../api/axios";
// import { uploadFiles, getDatasets, deleteDataset } from "../api/upload";

// export default function Upload() {
//   const [workspaces, setWorkspaces] = useState([]);
//   const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);
//   const [selectedFiles, setSelectedFiles] = useState([]);
//   const [datasets, setDatasets] = useState([]);
//   const [status, setStatus] = useState("");
//   const [error, setError] = useState("");
//   const [uploading, setUploading] = useState(false);
//   const [etlRunning, setEtlRunning] = useState({});

//   const fetchDatasets = async (wsId) => {
//     try {
//       const res = await getDatasets(wsId);
//       setDatasets(res.data);
//     } catch {
//       setError("Failed to load datasets");
//     }
//   };

//   useEffect(() => {
//     getWorkspaces().then((res) => {
//       setWorkspaces(res.data);
//       if (res.data.length > 0) setActiveWorkspaceId(res.data[0].id);
//     });
//   }, []);

//   useEffect(() => {
//     if (activeWorkspaceId) fetchDatasets(activeWorkspaceId);
//   }, [activeWorkspaceId]);

//   const handleUpload = async () => {
//     if (selectedFiles.length === 0) return;
//     setUploading(true);
//     setStatus("Uploading & processing data...");
//     setError("");
//     try {
//       await uploadFiles(activeWorkspaceId, selectedFiles);
//       setStatus("✅ Upload & ETL complete! Your data is ready.");
//       setSelectedFiles([]);
//       fetchDatasets(activeWorkspaceId);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Upload failed");
//       setStatus("");
//     } finally {
//       setUploading(false);
//     }
//   };

//   const handleRunETL = async (datasetId) => {
//     setEtlRunning((prev) => ({ ...prev, [datasetId]: true }));
//     try {
//       await api.post(`/etl/run/${datasetId}`);
//       await fetchDatasets(activeWorkspaceId);
//     } catch (err) {
//       setError(`ETL failed: ${err.response?.data?.detail || "Unknown error"}`);
//     } finally {
//       setEtlRunning((prev) => ({ ...prev, [datasetId]: false }));
//     }
//   };
//   const handleDelete = async (datasetId) => {
//     if (!window.confirm("Delete this dataset? This cannot be undone.")) return;
//     try {
//       await deleteDataset(datasetId);
//       fetchDatasets();
//     } catch {
//       setError("Failed to delete dataset");
//     }
//   };
//   return (
//     <div>
//       <Navbar />
//       <div style={{ display: "flex" }}>
//         <Sidebar />
//         <main style={{ flex: 1, padding: 24 }}>
//           <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
//             <h2>Upload Datasets</h2>
//             <select
//               value={activeWorkspaceId || ""}
//               onChange={(e) => setActiveWorkspaceId(Number(e.target.value))}
//             >
//               {workspaces.map((ws) => (
//                 <option key={ws.id} value={ws.id}>{ws.name}</option>
//               ))}
//             </select>
//           </div>

//           <UploadBox onFilesSelected={setSelectedFiles} />

//           {selectedFiles.length > 0 && (
//             <div style={{ marginTop: 12 }}>
//               <p>{selectedFiles.length} file(s) selected:</p>
//               <ul>
//                 {selectedFiles.map((f) => <li key={f.name}>{f.name} ({(f.size / 1024).toFixed(1)} KB)</li>)}
//               </ul>
//               <button onClick={handleUpload} disabled={uploading}>
//                 {uploading ? "⏳ Processing..." : "Upload & Process"}
//               </button>
//             </div>
//           )}

//           {status && <p style={{ color: "green", marginTop: 8 }}>{status}</p>}
//           {error && <p style={{ color: "red", marginTop: 8 }}>{error}</p>}

//           <h3 style={{ marginTop: 32 }}>Uploaded Datasets</h3>
//           {datasets.length === 0 ? (
//             <p style={{ color: "#888" }}>No datasets uploaded yet. Drop a CSV file above to get started.</p>
//           ) : (
//             <table style={{ width: "100%", borderCollapse: "collapse" }}>
//                <thead>
//                 <tr style={{ textAlign: "left", borderBottom: "2px solid #ddd", background: "#fafafa" }}>
//                   <th style={{ padding: "8px 12px" }}>Filename</th>
//                   <th style={{ padding: "8px 12px" }}>Rows</th>
//                   <th style={{ padding: "8px 12px" }}>Columns</th>
//                   <th style={{ padding: "8px 12px" }}>Size</th>
//                   <th style={{ padding: "8px 12px" }}>Status</th>
//                   <th style={{ padding: "8px 12px" }}>Actions</th>
//                 </tr>
//               </thead> 
            
          
//               <tbody>
              
//                 {datasets.map((ds) => (
//                   <tr key={ds.id} style={{ borderBottom: "1px solid #eee" }}>
//                     <td style={{ padding: "8px 12px" }}>{ds.original_filename}</td>
//                     <td style={{ padding: "8px 12px" }}>{ds.row_count?.toLocaleString() ?? "—"}</td>
//                     <td style={{ padding: "8px 12px" }}>{ds.column_count ?? "—"}</td>
//                     <td style={{ padding: "8px 12px" }}>{(ds.file_size / 1024).toFixed(1)} KB</td>
//                     <td style={{ padding: "8px 12px" }}>
//                       {ds.is_processed === 1 ? (
//                         <span style={{ color: "#27ae60", fontWeight: 600 }}>✅ Ready</span>
//                       ) : (
//                         <span style={{ color: "#e67e22", fontWeight: 600 }}>⏳ Pending ETL</span>
//                       )}
//                     </td>
//                     <td style={{ padding: "8px 12px" }}>
//                       {ds.is_processed !== 1 && (
//                         <button
//                           onClick={() => handleRunETL(ds.id)}
//                           disabled={etlRunning[ds.id]}
//                           style={{ fontSize: 12 }}
//                         >
//                           {etlRunning[ds.id] ? "Running..." : "Run ETL"}
//                         </button>
//                       )}
//                     </td>
//                     <td>{ds.original_filename}</td>
//                   <td>{ds.row_count ?? "-"}</td>
//                   <td>{ds.column_count ?? "-"}</td>
//                   <td>{(ds.file_size / 1024).toFixed(1)}</td>
//                   <td><button onClick={() => handleDelete(ds.id)} style={{ color: "#e74c3c" }}>Delete</button></td>
//                   </tr>
//                 ))}
                
//               </tbody>
//             </table>
//           )}
//         </main>
//       </div>
//     </div>
//   );
// }
import { useState, useEffect, useCallback } from "react";
import { useLocation } from "react-router-dom";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import UploadBox from "../components/UploadBox";
import { uploadFiles, getDatasets, deleteDataset } from "../api/upload";
import { getWorkspaces } from "../api/workspace";

export default function Upload() {
  const location = useLocation();
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [status, setStatus] = useState("");
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

  const fetchDatasets = useCallback(async () => {
    if (!activeWorkspaceId) return;
    try {
      const res = await getDatasets(activeWorkspaceId);
      setDatasets(res.data);
    } catch {
      setError("Failed to load datasets");
    }
  }, [activeWorkspaceId]);

  useEffect(() => { fetchDatasets(); }, [fetchDatasets]);

  const handleUpload = async () => {
    if (selectedFiles.length === 0 || !activeWorkspaceId) return;
    setStatus("Uploading...");
    setError("");
    try {
      await uploadFiles(activeWorkspaceId, selectedFiles);
      setStatus("Upload successful");
      setSelectedFiles([]);
      fetchDatasets();

      setTimeout(() => {
        setStatus((prev) => prev === "Upload successful" ? "" : prev);
      }, 4000);
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed");
      setStatus("");
    }
  };

  const handleDelete = async (datasetId) => {
    if (!window.confirm("Delete this dataset? This cannot be undone.")) return;
    try {
      await deleteDataset(datasetId);
      fetchDatasets();
    } catch {
      setError("Failed to delete dataset");
    }
  };

  return (
    <div className="app-container">
      <Sidebar />
      <div className="dp-main">
        <Navbar title="Upload Datasets" subtitle="Manage the CSV files powering your workspace" />
        <div className="dp-content">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
            <h2 style={{ margin: 0 }}>Dataset Management</h2>
            <select
              value={activeWorkspaceId || ""}
              onChange={(e) => setActiveWorkspaceId(Number(e.target.value))}
              style={{ background: "var(--bg-input)", color: "var(--text-primary)", border: "1px solid var(--border-color)", borderRadius: 8, padding: "8px 16px", flex: "1 1 auto", maxWidth: 300 }}
            >
              {workspaces.map((ws) => <option key={ws.id} value={ws.id}>{ws.name}</option>)}
            </select>
          </div>

          <div className="dp-card animate-fade-in" style={{ marginBottom: 32 }}>
            <UploadBox onFilesSelected={setSelectedFiles} />

            {selectedFiles.length > 0 && (
              <div style={{ marginTop: 24, padding: 16, background: "var(--bg-hover)", borderRadius: "var(--radius-sm)" }}>
                <p style={{ fontWeight: 500, marginBottom: 12 }}>{selectedFiles.length} file(s) ready to upload:</p>
                <ul style={{ margin: "0 0 16px 0", paddingLeft: 20, color: "var(--text-secondary)" }}>
                  {selectedFiles.map((f) => <li key={f.name}>{f.name} ({(f.size / 1024).toFixed(1)} KB)</li>)}
                </ul>
                <div style={{ display: "flex", gap: 12 }}>
                  <button onClick={handleUpload}>{status === "Uploading..." ? "Uploading..." : "Upload Files"}</button>
                  <button className="secondary" onClick={() => setSelectedFiles([])}>Cancel</button>
                </div>
              </div>
            )}
            
            {status && status !== "Uploading..." && <p style={{ color: "var(--accent-green)", margin: "16px 0 0", padding: "12px", background: "rgba(46, 204, 113, 0.1)", borderRadius: 8 }}>✅ {status}</p>}
            {error && <p style={{ color: "var(--accent-red)", margin: "16px 0 0", padding: "12px", background: "rgba(231, 76, 60, 0.1)", borderRadius: 8 }}>❌ {error}</p>}
          </div>

          <div className="dp-card animate-fade-in" style={{ animationDelay: "0.1s" }}>
            <h3 style={{ margin: "0 0 24px 0" }}>Uploaded Datasets</h3>
            {datasets.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-secondary)" }}>
                No datasets in this workspace yet. Upload a CSV to begin.
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th>Perfect Rows</th>
                      {/* <th>Rows Removed</th> */}
                      <th>Columns</th>
                      <th>Size (KB)</th>
                      <th>Status</th>
                      <th style={{ textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {datasets.map((ds) => (
                      <tr key={ds.id}>
                        <td style={{ fontWeight: 500, color: "var(--text-heading)" }}>{ds.original_filename}</td>
                        <td>{ds.row_count?.toLocaleString() ?? "—"}</td>
                        {/* <td>
                          {ds.rows_removed !== undefined && ds.rows_removed > 0 
                            ? <span style={{color: "var(--accent-red)"}}>{ds.rows_removed}</span> 
                            : ds.rows_removed === 0 ? "0" : "—"}
                        </td> */}
                        <td>{ds.column_count ?? "—"}</td>
                        <td>{(ds.file_size / 1024).toFixed(1)}</td>
                        <td>
                          {ds.is_processed === 1 ? (
                            <span className="dp-badge success">Ready</span>
                          ) : (
                            <span className="dp-badge warning">Processing</span>
                          )}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <button className="secondary danger" style={{ padding: "6px 12px", fontSize: 13 }} onClick={() => handleDelete(ds.id)}>Delete</button>
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