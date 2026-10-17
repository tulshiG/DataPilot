import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { loginUser } from "../api/auth.js";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const res = await loginUser(form);
      login(res.data.access_token);
      navigate("/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed");
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "url('/premium-bg.svg') center/cover, var(--bg-primary)" }}>
      <div className="dp-card animate-fade-in" style={{ width: 400, padding: 40, textAlign: "center" }}>
        <h2 style={{ fontSize: 28, marginBottom: 8 }}>Welcome back</h2>
        <p style={{ color: "var(--text-secondary)", marginBottom: 32 }}>Sign in to your DataPilot account</p>
        
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <input name="email" type="email" placeholder="Email address" onChange={handleChange} required style={{ width: "100%", boxSizing: "border-box" }} />
          <input name="password" type="password" placeholder="Password" onChange={handleChange} required style={{ width: "100%", boxSizing: "border-box" }} />
          <button type="submit" style={{ width: "100%", marginTop: 8 }}>Sign In</button>
        </form>
        {error && <p style={{ color: "var(--accent-red)", marginTop: 16, fontSize: 13, background: "rgba(231,76,60,0.1)", padding: 8, borderRadius: 8 }}>{error}</p>}
        <p style={{ marginTop: 24, fontSize: 14, color: "var(--text-secondary)" }}>
          Don't have an account? <Link to="/register" style={{ fontWeight: 600 }}>Create one</Link>
        </p>
      </div>
    </div>
  );
}