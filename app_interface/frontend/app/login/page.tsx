"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import "./login.css";

type LoginResponse = {
  success: boolean;
  user_id?: string;
  role?: string;
  message: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("employee_user");
  const [password, setPassword] = useState("pass123");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [demoInfo, setDemoInfo] = useState(false);

  const demoUsers = [
    { username: "employee_user", password: "pass123", role: "employee", desc: "General access" },
    { username: "finance_user", password: "pass123", role: "finance", desc: "Finance + general" },
    { username: "engineering_user", password: "pass123", role: "engineering", desc: "Engineering + general" },
    { username: "marketing_user", password: "pass123", role: "marketing", desc: "Marketing + general" },
    { username: "ceo_user", password: "pass123", role: "c_level", desc: "Full access" },
  ];

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data: LoginResponse = await res.json();

      if (data.success) {
        // Store in sessionStorage for the chat page
        sessionStorage.setItem("userId", data.user_id ?? "");
        sessionStorage.setItem("role", data.role ?? "");
        // Navigate to chat page
        router.push("/chat");
      } else {
        setError(data.message || "Login failed. Please try again.");
      }
    } catch (err) {
      setError("Connection error. Is the backend running?");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function setDemoUser(user: (typeof demoUsers)[0]) {
    setUsername(user.username);
    setPassword(user.password);
  }

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-card">
          <div className="login-header">
            <h1 className="login-title">FinBot</h1>
            <p className="login-subtitle">Enterprise Knowledge Assistant</p>
            <div className="login-divider"></div>
          </div>

          <form onSubmit={handleLogin} className="login-form">
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                disabled={loading}
                autoComplete="username"
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                disabled={loading}
                autoComplete="current-password"
              />
            </div>

            {error && <div className="error-message">{error}</div>}

            <button type="submit" className="login-button" disabled={loading}>
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>

          <div className="login-divider"></div>

          <div className="demo-section">
            <button
              type="button"
              className="demo-toggle"
              onClick={() => setDemoInfo(!demoInfo)}
            >
              {demoInfo ? "▼" : "▶"} Demo Users
            </button>

            {demoInfo && (
              <div className="demo-users">
                <p className="demo-note">Click to load demo credentials:</p>
                {demoUsers.map((user, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="demo-user-btn"
                    onClick={() => setDemoUser(user)}
                    title={user.desc}
                  >
                    <span className="demo-user-name">{user.username}</span>
                    <span className="demo-user-role">{user.role}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="login-footer">
            <p>Component 5: RBAC-aware authentication</p>
            <p>Your role determines which documents you can access.</p>
            <button
              type="button"
              className="admin-login-link"
              onClick={() => router.push("/admin/login")}
            >
              Admin Login
            </button>
          </div>
        </div>

        <div className="login-info">
          <h3>🔐 About This System</h3>
          <ul>
            <li><strong>Role-Based Access Control</strong> - Different roles see different documents</li>
            <li><strong>Semantic Routing</strong> - Questions routed to relevant collections</li>
            <li><strong>Guardrails</strong> - Input validation + output grounding checks</li>
            <li><strong>Source Citations</strong> - All answers cite their sources</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
