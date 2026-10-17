// import { useState } from "react";
// import { useNavigate, Link } from "react-router-dom";
// import { registerUser } from "../api/auth.js";


// export default function Register() {
//   const [form, setForm] = useState({ full_name: "", email: "", password: "" });
//   const [error, setError] = useState("");
//   const navigate = useNavigate();

//   const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

//   const handleSubmit = async (e) => {
//     e.preventDefault();
//     setError("");
//     try {
//       await registerUser(form);
//       navigate("/login");
//     } catch (err) {
//       setError(err.response?.data?.detail || "Registration failed");
//     }
//   };

//   return (
//     <div style={{ maxWidth: 400, margin: "80px auto" }}>
//       <h2>Create Account</h2>
//       <form onSubmit={handleSubmit}>
//         <input name="full_name" placeholder="Full Name" onChange={handleChange} required />
//         <input name="email" type="email" placeholder="Email" onChange={handleChange} required />
//         <input name="password" type="password" placeholder="Password" onChange={handleChange} required />
//         <button type="submit">Register</button>
//       </form>
//       {error && <p style={{ color: "red" }}>{error}</p>}
//       <p>Already have an account? <Link to="/login">Login</Link></p>
//     </div>
//   );
// }

import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { registerUser } from "../api/auth.js";

export default function Register() {
  // 1. Changed full_name to username to match your Pydantic schema
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await registerUser(form);
      navigate("/login");
    } catch (err) {
      // 2. Extract and format validation errors cleanly to prevent object rendering crashes
      const backendError = err.response?.data?.detail;
      if (Array.isArray(backendError)) {
        // Formats a Pydantic validation array into a clean string (e.g., "body.username: Field required")
        const friendlyMsg = backendError.map(e => `${e.loc.join('.')}: ${e.msg}`).join(", ");
        setError(friendlyMsg);
      } else {
        setError(backendError || "Registration failed");
      }
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "url('/premium-bg.svg') center/cover, var(--bg-primary)" }}>
      <div className="dp-card animate-fade-in" style={{ width: 400, padding: 40, textAlign: "center" }}>
        <h2 style={{ fontSize: 28, marginBottom: 8 }}>Create Account</h2>
        <p style={{ color: "var(--text-secondary)", marginBottom: 32 }}>Join DataPilot to start analyzing</p>
        
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <input name="full_name" placeholder="Full name" onChange={handleChange} required style={{ width: "100%", boxSizing: "border-box" }} />
          <input name="email" type="email" placeholder="Email address" onChange={handleChange} required style={{ width: "100%", boxSizing: "border-box" }} />
          <input name="password" type="password" placeholder="Password" onChange={handleChange} required style={{ width: "100%", boxSizing: "border-box" }} />
          <button type="submit" style={{ width: "100%", marginTop: 8 }}>Sign Up</button>
        </form>
        {error && <p style={{ color: "var(--accent-red)", marginTop: 16, fontSize: 13, background: "rgba(231,76,60,0.1)", padding: 8, borderRadius: 8 }}>{error}</p>}
        <p style={{ marginTop: 24, fontSize: 14, color: "var(--text-secondary)" }}>
          Already have an account? <Link to="/login" style={{ fontWeight: 600 }}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}