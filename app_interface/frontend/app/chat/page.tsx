"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import "./chat.css";

type ChatResponse = {
  blocked: boolean;
  answer: string;
  route_name: string | null;
  role: string;
  collections_used: string[];
  sources: { source_document: string; page_number: number | null; collection?: string; score?: number }[];
  guardrail_triggers: string[];
  guardrail_warnings: string[];
};

type ChatMessage = {
  query: string;
  response: ChatResponse;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function ChatPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [chatSessionId, setChatSessionId] = useState<string>("");
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [pageLoaded, setPageLoaded] = useState(false);

  function generateSessionId(baseUserId: string) {
    return `${baseUserId}-${Date.now()}`;
  }

  useEffect(() => {
    // Check if user is logged in
    const storedUserId = sessionStorage.getItem("userId");
    const storedRole = sessionStorage.getItem("role");

    if (!storedUserId || !storedRole) {
      // Not logged in, redirect to login
      router.push("/login");
    } else {
      setUserId(storedUserId);
      setRole(storedRole);
      setChatSessionId(generateSessionId(storedUserId));
      setPageLoaded(true);
    }
  }, [router]);

  async function handleChat() {
    if (!userId || !role || !query.trim()) return;

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          role,
          query,
          session_id: chatSessionId || userId,
        }),
      });
      const data: ChatResponse = await res.json();
      setChat((prev) => [...prev, { query, response: data }]);
      setQuery("");
    } catch (err) {
      console.error("Chat error:", err);
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    sessionStorage.removeItem("userId");
    sessionStorage.removeItem("role");
    router.push("/login");
  }

  function handleNewChat() {
    if (!userId) return;
    setChat([]);
    setQuery("");
    setChatSessionId(generateSessionId(userId));
  }

  function handleClearChat() {
    setChat([]);
    setShowClearConfirm(false);
  }

  if (!pageLoaded) {
    return (
      <div className="chat-page">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-page">
      <div className="chat-container">
        {/* Header */}
        <div className="chat-header">
          <div className="header-left">
            <h1 className="chat-title">FinBot</h1>
            <p className="header-role">
              <span className="role-badge" data-role={role}>{role}</span>
              <span className="user-id">{userId}</span>
            </p>
          </div>
          <button className="logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </div>

        {/* Chat Area */}
        <div className="chat-area">
          {chat.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">💬</div>
              <h2>Start a Conversation</h2>
              <p>Ask questions about company policies, finance, engineering, or marketing documents.</p>
              <div className="example-queries">
                <p className="example-label">Try asking:</p>
                <button className="example-btn" onClick={() => setQuery("What is the leave policy?")}>
                  What is the leave policy?
                </button>
                <button className="example-btn" onClick={() => setQuery("How do I request time off?")}>
                  How do I request time off?
                </button>
                <button className="example-btn" onClick={() => setQuery("What benefits are available?")}>
                  What benefits are available?
                </button>
              </div>
            </div>
          ) : (
            <div className="chat-messages">
              {chat.map((msg, idx) => (
                <div key={idx} className="message-pair">
                  {/* User Query */}
                  <div className="message user-message">
                    <div className="message-content">{msg.query}</div>
                  </div>

                  {/* Bot Response */}
                  <div className={`message bot-message ${msg.response.blocked ? "blocked" : ""}`}>
                    <div className="message-content">{msg.response.answer}</div>

                    {/* Metadata */}
                    <div className="message-meta">
                      <div className="route-info">
                        Route: <strong>{msg.response.route_name || "-"}</strong>
                      </div>
                      <div className="collections-info">
                        Collections: <strong>{msg.response.collections_used.join(", ") || "none"}</strong>
                      </div>
                    </div>

                    {/* Guardrail Warnings */}
                    {msg.response.guardrail_triggers.length > 0 && (
                      <div className="guardrail-warning">
                        <strong>⚠️ Guardrails:</strong> {msg.response.guardrail_triggers.join(", ")}
                      </div>
                    )}

                    {msg.response.guardrail_warnings.length > 0 && (
                      <div className="guardrail-warnings-detail">
                        {msg.response.guardrail_warnings.map((w, i) => (
                          <div key={i} className="warning-item">• {w}</div>
                        ))}
                      </div>
                    )}

                    {/* Sources */}
                    {msg.response.sources.length > 0 && (
                      <div className="sources-section">
                        <strong>📄 Sources:</strong>
                        <ul className="sources-list">
                          {msg.response.sources.map((s, i) => (
                            <li key={i}>
                              <span className="source-doc">{s.source_document}</span>
                              <span className="source-page">p. {s.page_number}</span>
                              {s.collection && <span className="source-collection">{s.collection}</span>}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="chat-input-area">
          <div className="chat-tools-row">
            <button
              type="button"
              className="tool-btn"
              onClick={handleNewChat}
              disabled={loading || !userId}
            >
              New Chat
            </button>
            <button
              type="button"
              className="tool-btn danger"
              onClick={() => setShowClearConfirm(true)}
              disabled={loading || chat.length === 0}
            >
              Clear All
            </button>
            <span className="chat-count">Messages: {chat.length}</span>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (query.trim()) handleChat();
            }}
            className="chat-form"
          >
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && e.ctrlKey) {
                  e.preventDefault();
                  if (query.trim()) handleChat();
                }
              }}
              placeholder="Ask a question... (Ctrl+Enter to send)"
              rows={3}
              disabled={loading}
              className="chat-input"
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="send-btn"
            >
              {loading ? "Thinking..." : "Send"}
            </button>
          </form>
          <p className="input-hint">
            💡 Tip: Ctrl+Enter for quick send. Your role ({role}) determines which documents you can access.
          </p>
        </div>

        {showClearConfirm && (
          <div className="confirm-overlay" role="dialog" aria-modal="true">
            <div className="confirm-modal">
              <h3>Clear all messages?</h3>
              <p>This will remove every message in the current chat window.</p>
              <div className="confirm-actions">
                <button
                  type="button"
                  className="confirm-btn"
                  onClick={() => setShowClearConfirm(false)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="confirm-btn danger"
                  onClick={handleClearChat}
                >
                  Yes, Clear All
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
