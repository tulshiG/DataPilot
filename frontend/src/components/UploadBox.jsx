import { useState, useRef } from "react";

export default function UploadBox({ onFilesSelected }) {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    onFilesSelected(Array.from(e.dataTransfer.files));
  };

  const handleChange = (e) => {
    onFilesSelected(Array.from(e.target.files));
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
      onDragLeave={() => setDragActive(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      style={{
        border: `2px dashed ${dragActive ? "var(--accent-purple)" : "var(--border-light)"}`,
        borderRadius: "var(--radius-md)",
        padding: "60px 40px",
        textAlign: "center",
        background: dragActive ? "var(--bg-hover)" : "var(--bg-card)",
        cursor: "pointer",
        transition: "all 0.2s ease",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16
      }}
    >
      <div style={{
        width: 64, height: 64, borderRadius: "50%",
        background: "rgba(124, 108, 246, 0.1)", display: "flex",
        alignItems: "center", justifyContent: "center",
        color: "var(--accent-purple)", fontSize: 28
      }}>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="17 8 12 3 7 8"></polyline>
          <line x1="12" y1="3" x2="12" y2="15"></line>
        </svg>
      </div>
      <div>
        <h3 style={{ margin: "0 0 8px 0", fontSize: 18, color: "var(--text-heading)" }}>Click or drag file to this area to upload</h3>
        <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: 14 }}>Support for a single or bulk CSV upload.</p>
      </div>
      <input 
        ref={inputRef} 
        type="file" 
        accept=".csv" 
        multiple 
        onChange={handleChange} 
        style={{ display: "none" }} 
      />
    </div>
  );
}