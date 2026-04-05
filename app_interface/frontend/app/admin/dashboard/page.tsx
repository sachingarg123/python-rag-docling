'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import './admin-dashboard.css';

interface User {
  id: string;
  name: string;
  role: string;
  status: 'active' | 'blocked';
  lastActive: string;
}

interface QueryStat {
  id: string;
  query: string;
  responseTime: number;
  timestamp: string;
  user: string;
}

interface Document {
  id: string;
  name: string;
  collection: string;
  status: 'indexed' | 'failed' | 'pending';
  size: string;
  uploadedAt: string;
}

interface GuardrailEvent {
  id: string;
  type: string;
  query: string;
  timestamp: string;
  severity: 'info' | 'warning' | 'critical';
}

interface HealthStatus {
  api: 'healthy' | 'degraded' | 'down';
  database: 'healthy' | 'degraded' | 'down';
  vectorStore: 'healthy' | 'degraded' | 'down';
  uptime: string;
}

export default function AdminDashboard() {
  const router = useRouter();
  const [adminUser, setAdminUser] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);

  // State for real data from API
  const [users, setUsers] = useState<User[]>([]);

  // Modal states
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showDocumentModal, setShowDocumentModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [newUserForm, setNewUserForm] = useState({ username: '', password: '', role: 'employee' });
  const [passwordForm, setPasswordForm] = useState({ newPassword: '' });
  const [documentForm, setDocumentForm] = useState({ name: '', collection: 'general' });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Mock data for queries, documents, guardrails
  const [queries, setQueries] = useState<QueryStat[]>([
    { id: '1', query: 'What is the leave policy?', responseTime: 1240, timestamp: '2 min ago', user: 'employee_user' },
    { id: '2', query: 'Show company vision', responseTime: 890, timestamp: '5 min ago', user: 'ceo_user' },
    { id: '3', query: 'Finance reports Q1', responseTime: 2100, timestamp: '10 min ago', user: 'finance_user' },
  ]);

  const [documents, setDocuments] = useState<Document[]>([
    { id: '1', name: 'employee_handbook.pdf', collection: 'general', status: 'indexed', size: '2.3 MB', uploadedAt: '2024-04-01' },
    { id: '2', name: 'finance_policies.pdf', collection: 'finance', status: 'indexed', size: '1.8 MB', uploadedAt: '2024-04-02' },
    { id: '3', name: 'engineering_guide.pdf', collection: 'engineering', status: 'pending', size: '5.2 MB', uploadedAt: '2 hours ago' },
  ]);

  const [guardrails, setGuardrails] = useState<GuardrailEvent[]>([
    { id: '1', type: 'off_topic', query: 'Tell me a joke', timestamp: '1 hour ago', severity: 'info' },
    { id: '2', type: 'prompt_injection', query: 'ignore instructions...', timestamp: '30 min ago', severity: 'critical' },
    { id: '3', type: 'rate_limit', query: 'Multiple rapid queries', timestamp: '10 min ago', severity: 'warning' },
  ]);

  const [health, setHealth] = useState<HealthStatus>({
    api: 'healthy',
    database: 'healthy',
    vectorStore: 'healthy',
    uptime: '99.8%',
  });

  // Fetch users from API
  const fetchUsers = async () => {
    try {
      const response = await fetch('http://localhost:8000/admin/users');
      const data = await response.json();
      setUsers(data.users);
    } catch (err) {
      console.error('Failed to fetch users:', err);
    }
  };

  useEffect(() => {
    // Check admin authentication
    const admin = sessionStorage.getItem('adminUser');
    if (!admin) {
      router.push('/admin/login');
      return;
    }
    setAdminUser(admin);
    fetchUsers();
    setLoading(false);
  }, [router]);

  const handleLogout = () => {
    sessionStorage.removeItem('adminUser');
    sessionStorage.removeItem('adminRole');
    sessionStorage.removeItem('adminLoginTime');
    router.push('/admin/login');
  };

  // Add User Handler
  const handleAddUser = async () => {
    if (!newUserForm.username || !newUserForm.password || !newUserForm.role) {
      setError('Please fill all fields');
      return;
    }

    try {
      const response = await fetch('http://localhost:8000/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newUserForm),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to add user');
      }

      setSuccess('User added successfully!');
      setNewUserForm({ username: '', password: '', role: 'employee' });
      setShowAddUserModal(false);
      await fetchUsers(); // Refresh user list
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add user');
      setTimeout(() => setError(''), 3000);
    }
  };

  // Toggle User Status Handler (Block/Unblock)
  const handleToggleUserStatus = async (userId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/admin/users/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to toggle user status');
      }

      setSuccess('User status updated!');
      await fetchUsers(); // Refresh user list
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update user');
      setTimeout(() => setError(''), 3000);
    }
  };

  // Change Password Handler
  const handleChangePassword = async () => {
    if (!selectedUser || !passwordForm.newPassword) {
      setError('Please enter a new password');
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/admin/users/${selectedUser.id}/password`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(passwordForm),
      });

      if (!response.ok) {
        throw new Error('Failed to update password');
      }

      setSuccess('Password updated successfully!');
      setPasswordForm({ newPassword: '' });
      setShowPasswordModal(false);
      setSelectedUser(null);
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update password');
      setTimeout(() => setError(''), 3000);
    }
  };

  // Upload Document Handler
  const handleUploadDocument = async () => {
    if (!documentForm.name || !documentForm.collection) {
      setError('Please fill all fields');
      return;
    }

    try {
      const response = await fetch('http://localhost:8000/admin/documents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(documentForm),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to upload document');
      }

      const data = await response.json();
      setSuccess(`Document "${data.name}" uploaded successfully!`);
      setDocumentForm({ name: '', collection: 'general' });
      setShowDocumentModal(false);
      // Add document to local list
      setDocuments([
        ...documents,
        {
          id: data.document_id,
          name: data.name,
          collection: documentForm.collection,
          status: 'pending',
          size: '0 MB',
          uploadedAt: new Date().toLocaleString(),
        },
      ]);
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload document');
      setTimeout(() => setError(''), 3000);
    }
  };

  // Delete Document Handler
  const handleDeleteDocument = async (docId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/admin/documents/${docId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete document');
      }

      setSuccess('Document deleted successfully!');
      setDocuments(documents.filter((d) => d.id !== docId));
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete document');
      setTimeout(() => setError(''), 3000);
    }
  };

  const toggleUserStatus = (userId: string) => {
    handleToggleUserStatus(userId);
  };

  const deleteDocument = (docId: string) => {
    handleDeleteDocument(docId);
  }

  if (loading) {
    return (
      <div className="admin-loading">
        <div className="admin-spinner"></div>
        <p>Loading admin panel...</p>
      </div>
    );
  }

  return (
    <div className="admin-dashboard">
      {/* Header */}
      <div className="admin-header">
        <div className="admin-header-left">
          <h1 className="admin-title">⚙️ Admin Dashboard</h1>
          <p className="admin-subtitle">Logged in as: <strong>{adminUser}</strong></p>
        </div>
        <button className="admin-logout-btn" onClick={handleLogout}>
          🚪 Logout
        </button>
      </div>

      {/* Tabs */}
      <div className="admin-tabs">
        <button
          className={`admin-tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          📊 Overview
        </button>
        <button
          className={`admin-tab ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          👥 Users ({users.length})
        </button>
        <button
          className={`admin-tab ${activeTab === 'analytics' ? 'active' : ''}`}
          onClick={() => setActiveTab('analytics')}
        >
          📈 Analytics
        </button>
        <button
          className={`admin-tab ${activeTab === 'documents' ? 'active' : ''}`}
          onClick={() => setActiveTab('documents')}
        >
          📄 Documents
        </button>
        <button
          className={`admin-tab ${activeTab === 'guardrails' ? 'active' : ''}`}
          onClick={() => setActiveTab('guardrails')}
        >
          🚨 Guardrails
        </button>
        <button
          className={`admin-tab ${activeTab === 'health' ? 'active' : ''}`}
          onClick={() => setActiveTab('health')}
        >
          ✅ Health
        </button>
      </div>

      {/* Content */}
      <div className="admin-content">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="admin-overview">
            <h2>System Overview</h2>
            <div className="admin-stats-grid">
              <div className="admin-stat-card">
                <h3>👥 Active Users</h3>
                <div className="admin-stat-value">{users.filter((u) => u.status === 'active').length}</div>
                <p>Out of {users.length} total</p>
              </div>
              <div className="admin-stat-card">
                <h3>💬 Queries Today</h3>
                <div className="admin-stat-value">{queries.length}</div>
                <p>Avg response: {Math.round(queries.reduce((a, b) => a + b.responseTime, 0) / queries.length)}ms</p>
              </div>
              <div className="admin-stat-card">
                <h3>📚 Documents</h3>
                <div className="admin-stat-value">{documents.length}</div>
                <p>{documents.filter((d) => d.status === 'indexed').length} indexed</p>
              </div>
              <div className="admin-stat-card">
                <h3>🚨 Alerts</h3>
                <div className="admin-stat-value">{guardrails.filter((g) => g.severity === 'critical').length}</div>
                <p>Critical events</p>
              </div>
            </div>
          </div>
        )}

      {/* Users Tab */}
        {activeTab === 'users' && (
          <div className="admin-users">
            <div className="admin-section-header">
              <h2>User Management</h2>
              <button className="admin-add-btn" onClick={() => setShowAddUserModal(true)}>
                ➕ Add User
              </button>
            </div>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last Active</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.name}</td>
                    <td>
                      <span className={`admin-role admin-role-${user.role}`}>{user.role}</span>
                    </td>
                    <td>
                      <span className={`admin-status admin-status-${user.status}`}>{user.status}</span>
                    </td>
                    <td>{user.lastActive}</td>
                    <td className="admin-actions-cell">
                      <button
                        className={`admin-action-btn ${user.status === 'blocked' ? 'unblock' : 'block'}`}
                        onClick={() => toggleUserStatus(user.id)}
                      >
                        {user.status === 'active' ? '🚫 Block' : '✅ Unblock'}
                      </button>
                      <button
                        className="admin-action-btn edit-password"
                        onClick={() => {
                          setSelectedUser(user);
                          setPasswordForm({ newPassword: '' });
                          setShowPasswordModal(true);
                        }}
                      >
                        🔐 Change Password
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <div className="admin-analytics">
            <h2>Query Analytics</h2>
            <p className="admin-section-subtitle">Recent queries and response times</p>
            <div className="admin-query-list">
              {queries.map((query) => (
                <div key={query.id} className="admin-query-item">
                  <div className="admin-query-info">
                    <p className="admin-query-text">"{query.query}"</p>
                    <p className="admin-query-meta">User: {query.user} • {query.timestamp}</p>
                  </div>
                  <div className={`admin-response-time ${query.responseTime > 2000 ? 'slow' : 'normal'}`}>
                    ⏱️ {query.responseTime}ms
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Documents Tab */}
        {activeTab === 'documents' && (
          <div className="admin-documents">
            <div className="admin-section-header">
              <h2>Document Management</h2>
              <button className="admin-upload-btn" onClick={() => setShowDocumentModal(true)}>
                📤 Upload Document
              </button>
            </div>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Document Name</th>
                  <th>Collection</th>
                  <th>Status</th>
                  <th>Size</th>
                  <th>Uploaded</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id}>
                    <td>{doc.name}</td>
                    <td>{doc.collection}</td>
                    <td>
                      <span className={`admin-doc-status admin-doc-status-${doc.status}`}>{doc.status}</span>
                    </td>
                    <td>{doc.size}</td>
                    <td>{doc.uploadedAt}</td>
                    <td>
                      <button
                        className="admin-delete-btn"
                        onClick={() => deleteDocument(doc.id)}
                      >
                        🗑️ Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Guardrails Tab */}
        {activeTab === 'guardrails' && (
          <div className="admin-guardrails">
            <h2>Guardrail Events</h2>
            <p className="admin-section-subtitle">Monitored security and safety events</p>
            <div className="admin-guardrail-list">
              {guardrails.map((event) => (
                <div key={event.id} className={`admin-guardrail-item severity-${event.severity}`}>
                  <div className="admin-guardrail-header">
                    <span className={`admin-severity-badge admin-severity-${event.severity}`}>
                      {event.severity === 'critical' ? '🔴' : event.severity === 'warning' ? '🟡' : '🔵'}
                      {event.severity}
                    </span>
                    <span className="admin-event-type">{event.type}</span>
                    <span className="admin-event-time">{event.timestamp}</span>
                  </div>
                  <p className="admin-event-query">Query: "{event.query}"</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Health Tab */}
        {activeTab === 'health' && (
          <div className="admin-health">
            <h2>System Health</h2>
            <div className="admin-health-grid">
              <div className={`admin-health-card health-${health.api}`}>
                <h3>🔗 API Server</h3>
                <div className="admin-health-status">{health.api}</div>
                <p>Backend service status</p>
              </div>
              <div className={`admin-health-card health-${health.database}`}>
                <h3>🗄️ Database</h3>
                <div className="admin-health-status">{health.database}</div>
                <p>Qdrant vector store</p>
              </div>
              <div className={`admin-health-card health-${health.vectorStore}`}>
                <h3>📊 Vector Store</h3>
                <div className="admin-health-status">{health.vectorStore}</div>
                <p>Embedding service</p>
              </div>
              <div className="admin-health-card health-healthy">
                <h3>⏱️ Uptime</h3>
                <div className="admin-health-status">{health.uptime}</div>
                <p>System availability</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Notifications */}
      {error && (
        <div className="admin-notification error-notification">
          ❌ {error}
        </div>
      )}
      {success && (
        <div className="admin-notification success-notification">
          ✅ {success}
        </div>
      )}

      {/* Add User Modal */}
      {showAddUserModal && (
        <div className="admin-modal-overlay">
          <div className="admin-modal">
            <h2>Add New User</h2>
            <div className="admin-form-group">
              <label>Username</label>
              <input
                type="text"
                placeholder="Enter username"
                value={newUserForm.username}
                onChange={(e) => setNewUserForm({ ...newUserForm, username: e.target.value })}
              />
            </div>
            <div className="admin-form-group">
              <label>Password</label>
              <input
                type="password"
                placeholder="Enter password"
                value={newUserForm.password}
                onChange={(e) => setNewUserForm({ ...newUserForm, password: e.target.value })}
              />
            </div>
            <div className="admin-form-group">
              <label>Role</label>
              <select
                value={newUserForm.role}
                onChange={(e) => setNewUserForm({ ...newUserForm, role: e.target.value })}
              >
                <option value="employee">Employee</option>
                <option value="finance">Finance</option>
                <option value="engineering">Engineering</option>
                <option value="marketing">Marketing</option>
                <option value="c_level">C-Level</option>
              </select>
            </div>
            <div className="admin-modal-actions">
              <button className="admin-btn-cancel" onClick={() => setShowAddUserModal(false)}>
                Cancel
              </button>
              <button className="admin-btn-confirm" onClick={handleAddUser}>
                Add User
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Change Password Modal */}
      {showPasswordModal && selectedUser && (
        <div className="admin-modal-overlay">
          <div className="admin-modal">
            <h2>Change Password for {selectedUser.name}</h2>
            <div className="admin-form-group">
              <label>New Password</label>
              <input
                type="password"
                placeholder="Enter new password"
                value={passwordForm.newPassword}
                onChange={(e) => setPasswordForm({ newPassword: e.target.value })}
              />
            </div>
            <div className="admin-modal-actions">
              <button className="admin-btn-cancel" onClick={() => setShowPasswordModal(false)}>
                Cancel
              </button>
              <button className="admin-btn-confirm" onClick={handleChangePassword}>
                Update Password
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Document Upload Modal */}
      {showDocumentModal && (
        <div className="admin-modal-overlay">
          <div className="admin-modal">
            <h2>Upload Document</h2>
            <div className="admin-form-group">
              <label>Document Name</label>
              <input
                type="text"
                placeholder="e.g., employee_handbook.pdf"
                value={documentForm.name}
                onChange={(e) => setDocumentForm({ ...documentForm, name: e.target.value })}
              />
            </div>
            <div className="admin-form-group">
              <label>Collection</label>
              <select
                value={documentForm.collection}
                onChange={(e) => setDocumentForm({ ...documentForm, collection: e.target.value })}
              >
                <option value="general">General</option>
                <option value="finance">Finance</option>
                <option value="engineering">Engineering</option>
                <option value="marketing">Marketing</option>
              </select>
            </div>
            <div className="admin-modal-actions">
              <button className="admin-btn-cancel" onClick={() => setShowDocumentModal(false)}>
                Cancel
              </button>
              <button className="admin-btn-confirm" onClick={handleUploadDocument}>
                Upload
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="admin-footer">
        <p>FinBot Admin Panel • v1.0 • Last updated: {new Date().toLocaleString()}</p>
      </div>
    </div>
  );
}
