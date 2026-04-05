'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import './admin-login.css';

export default function AdminLogin() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Hardcoded admin credentials (in production, use backend validation)
  const ADMIN_CREDENTIALS = {
    username: 'admin',
    password: 'FinSolve@Admin2024',
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Simulate API call
    setTimeout(() => {
      if (
        username === ADMIN_CREDENTIALS.username &&
        password === ADMIN_CREDENTIALS.password
      ) {
        // Store admin session
        sessionStorage.setItem('adminUser', username);
        sessionStorage.setItem('adminRole', 'admin');
        sessionStorage.setItem('adminLoginTime', new Date().toISOString());

        // Redirect to dashboard
        router.push('/admin/dashboard');
      } else {
        setError('❌ Invalid admin credentials');
        setLoading(false);
      }
    }, 800);
  };

  return (
    <div className="admin-login-page">
      {/* Background gradient */}
      <div className="admin-login-bg"></div>

      {/* Login card */}
      <div className="admin-login-container">
        <div className="admin-login-card">
          {/* Header */}
          <div className="admin-login-header">
            <h1 className="admin-login-title">
              <span className="admin-icon">⚙️</span>
              FinBot Admin
            </h1>
            <p className="admin-login-subtitle">Enterprise Management System</p>
          </div>

          {/* Error message */}
          {error && <div className="admin-error-box">{error}</div>}

          {/* Form */}
          <form onSubmit={handleLogin} className="admin-login-form">
            <div className="admin-form-group">
              <label htmlFor="username" className="admin-form-label">
                Admin Username
              </label>
              <input
                id="username"
                type="text"
                placeholder="Enter admin username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="admin-form-input"
                disabled={loading}
                autoComplete="username"
              />
            </div>

            <div className="admin-form-group">
              <label htmlFor="password" className="admin-form-label">
                Admin Password
              </label>
              <input
                id="password"
                type="password"
                placeholder="Enter admin password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="admin-form-input"
                disabled={loading}
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              className="admin-login-button"
              disabled={loading || !username || !password}
            >
              {loading ? '🔐 Authenticating...' : '🔓 Enter Admin Panel'}
            </button>
          </form>

          {/* Demo credentials info */}
          <div className="admin-demo-box">
            <h3>📋 Demo Admin Credentials</h3>
            <div className="admin-demo-item">
              <strong>Username:</strong>
              <code>admin</code>
              <button
                type="button"
                className="admin-copy-btn"
                onClick={() => {
                  navigator.clipboard.writeText('admin');
                  setUsername('admin');
                }}
              >
                Copy
              </button>
            </div>
            <div className="admin-demo-item">
              <strong>Password:</strong>
              <code>FinSolve@Admin2024</code>
              <button
                type="button"
                className="admin-copy-btn"
                onClick={() => {
                  navigator.clipboard.writeText('FinSolve@Admin2024');
                  setPassword('FinSolve@Admin2024');
                }}
              >
                Copy
              </button>
            </div>
          </div>

          {/* Footer info */}
          <div className="admin-login-footer">
            <p>🔒 Admin access is restricted to authorized personnel only</p>
            <a href="/" className="admin-back-link">
              ← Back to main application
            </a>
          </div>
        </div>

        {/* System info sidebar */}
        <div className="admin-system-info">
          <h4>🖥️ System Information</h4>
          <div className="admin-info-item">
            <span>Environment:</span>
            <strong>Production</strong>
          </div>
          <div className="admin-info-item">
            <span>API Version:</span>
            <strong>1.0</strong>
          </div>
          <div className="admin-info-item">
            <span>Database:</span>
            <strong>Qdrant</strong>
          </div>
          <div className="admin-info-item">
            <span>Admin Routes:</span>
            <strong>Protected</strong>
          </div>
        </div>
      </div>
    </div>
  );
}
