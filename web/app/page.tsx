"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  sendStreamingMessage,
  fetchConversations,
  fetchProviders,
  fetchSettings,
  switchModel,
  updateSettings,
  setApiKey,
  deleteApiKey,
  deleteConversation,
  startOAuth,
  fetchAuthStatus,
  type ChatMessage,
  type ToolCall,
  type Conversation,
  type ProviderInfo,
  type AppSettings,
  type AuthProviderStatus,
} from "@/lib/api";

/* ═══════════════════════════════════════════════════════════════════
   Provider metadata for the auth screen
   ═══════════════════════════════════════════════════════════════════ */

const PROVIDER_META: Record<string, {
  name: string;
  icon: string;
  color: string;
  description: string;
  keyPrefix: string;
  signupUrl: string;
  envVar: string;
  models: string;
  supportsOAuth?: boolean;
}> = {
  openrouter: {
    name: "OpenRouter",
    icon: "🌐",
    color: "#6366f1",
    description: "186+ models from all providers. Free tier available.",
    keyPrefix: "sk-or-",
    signupUrl: "https://openrouter.ai/keys",
    envVar: "OPENROUTER_API_KEY",
    models: "GPT-4o, Claude, Gemini, Llama, Mistral, and 180+",
  },
  anthropic: {
    name: "Anthropic",
    icon: "🤖",
    color: "#d97706",
    description: "Claude models — best for coding and reasoning.",
    keyPrefix: "sk-ant-",
    signupUrl: "https://console.anthropic.com/settings/keys",
    envVar: "ANTHROPIC_API_KEY",
    models: "Claude Opus, Sonnet, Haiku",
  },
  google: {
    name: "Google AI",
    icon: "🔷",
    color: "#4285f4",
    description: "Gemini models — sign in with your Google account or use API key.",
    keyPrefix: "AIza",
    signupUrl: "https://aistudio.google.com/apikey",
    envVar: "GOOGLE_API_KEY",
    models: "Gemini 2.0 Flash, Gemini 2.5 Pro, Gemini 2.5 Flash",
    supportsOAuth: true,
  },
  openai: {
    name: "OpenAI",
    icon: "💚",
    color: "#10a37f",
    description: "GPT-4o and o1 reasoning models.",
    keyPrefix: "sk-",
    signupUrl: "https://platform.openai.com/api-keys",
    envVar: "OPENAI_API_KEY",
    models: "GPT-4o, GPT-4o-mini, o1-preview, o1-mini",
  },
  groq: {
    name: "Groq",
    icon: "⚡",
    color: "#f97316",
    description: "Ultra-fast inference, free tier available.",
    keyPrefix: "gsk_",
    signupUrl: "https://console.groq.com/keys",
    envVar: "GROQ_API_KEY",
    models: "Llama 3.3, Mixtral, Gemma",
  },
  deepseek: {
    name: "DeepSeek",
    icon: "🐋",
    color: "#2563eb",
    description: "Top-tier coding models at low cost.",
    keyPrefix: "sk-",
    signupUrl: "https://platform.deepseek.com/api_keys",
    envVar: "DEEPSEEK_API_KEY",
    models: "DeepSeek Chat, DeepSeek Coder",
  },
  mistral: {
    name: "Mistral",
    icon: "🌊",
    color: "#ff7000",
    description: "European AI models — efficient and powerful.",
    keyPrefix: "",
    signupUrl: "https://console.mistral.ai/api-keys",
    envVar: "MISTRAL_API_KEY",
    models: "Mistral Large, Mistral Small, Codestral",
  },
};

/* ═══════════════════════════════════════════════════════════════════
   NexCode Web — Full-Featured Chat App
   ═══════════════════════════════════════════════════════════════════ */

export default function Home() {
  // ── Core state ──────────────────────────────────────────────────
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // ── Sidebar & conversations ─────────────────────────────────────
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // ── Model & provider ────────────────────────────────────────────
  const [currentModel, setCurrentModel] = useState("moonshotai/kimi-k2.5");
  const [currentProvider, setCurrentProvider] = useState("openrouter");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [showModelSelector, setShowModelSelector] = useState(false);

  // ── Settings ────────────────────────────────────────────────────
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsTab, setSettingsTab] = useState<"general" | "auth" | "tools">("general");

  // ── Auth inline editing ─────────────────────────────────────────
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [editingKey, setEditingKey] = useState("");
  const [authStatus, setAuthStatus] = useState<Record<string, AuthProviderStatus>>({});
  const [oauthLoading, setOauthLoading] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Load data on mount ──────────────────────────────────────────
  useEffect(() => {
    fetchProviders().then(setProviders).catch(() => { });
    fetchSettings().then(setSettings).catch(() => { });
    fetchConversations().then(setConversations).catch(() => { });
    fetchAuthStatus().then(setAuthStatus).catch(() => { });
  }, []);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }, []);
  useEffect(scrollToBottom, [messages, scrollToBottom]);

  useEffect(() => {
    const el = inputRef.current;
    if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 200) + "px"; }
  }, [input]);

  const refreshConversations = useCallback(() => {
    fetchConversations().then(setConversations).catch(() => { });
  }, []);

  // ── Send message ────────────────────────────────────────────────
  const sendMessage = useCallback(() => {
    const text = input.trim();
    if (!text || isStreaming) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(), role: "user", content: text, timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);

    const aId = crypto.randomUUID();
    setMessages(prev => [...prev, {
      id: aId, role: "assistant", content: "", toolCalls: [], timestamp: new Date(),
    }]);

    sendStreamingMessage(text, sessionId, {
      onSessionCreated: (sid) => setSessionId(sid),
      onToken: (content) => {
        setMessages(prev => prev.map(m => m.id === aId ? { ...m, content } : m));
        scrollToBottom();
      },
      onToolStart: (tool, args) => {
        const tc: ToolCall = { id: crypto.randomUUID(), tool, arguments: args, status: "running" };
        setMessages(prev => prev.map(m =>
          m.id === aId ? { ...m, toolCalls: [...(m.toolCalls || []), tc] } : m
        ));
        scrollToBottom();
      },
      onToolEnd: (tool, result, success) => {
        setMessages(prev => prev.map(m => {
          if (m.id !== aId) return m;
          const updated = (m.toolCalls || []).map(tc =>
            tc.tool === tool && tc.status === "running"
              ? { ...tc, result, success, status: success ? "success" as const : "error" as const }
              : tc
          );
          return { ...m, toolCalls: updated };
        }));
      },
      onDone: (content, sid, model, provider) => {
        setMessages(prev => prev.map(m => m.id === aId ? { ...m, content } : m));
        setSessionId(sid);
        setCurrentModel(model);
        setCurrentProvider(provider);
        setIsStreaming(false);
        refreshConversations();
        scrollToBottom();
      },
      onError: (message) => {
        setMessages(prev => prev.map(m =>
          m.id === aId ? { ...m, content: `❌ Error: ${message}` } : m
        ));
        setIsStreaming(false);
      },
    });
  }, [input, isStreaming, sessionId, scrollToBottom, refreshConversations]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const handleNewChat = () => {
    setMessages([]); setSessionId(null); setSidebarOpen(false);
    inputRef.current?.focus();
  };

  const handleDeleteConv = async (id: string) => {
    await deleteConversation(id);
    if (sessionId === id) handleNewChat();
    refreshConversations();
  };

  const handleSwitchModel = async (providerId: string, model: string) => {
    await switchModel(providerId, model);
    setCurrentProvider(providerId);
    setCurrentModel(model);
    setShowModelSelector(false);
  };

  const handleSaveSettings = async () => {
    if (!settings) return;
    await updateSettings({
      max_tokens: settings.max_tokens,
      theme: settings.theme,
      permission_mode: settings.permission_mode,
    });
    setShowSettings(false);
  };

  // ── Auth handlers ───────────────────────────────────────────────
  const handleAddKey = async (provider: string) => {
    if (!editingKey.trim()) return;
    await setApiKey(provider, editingKey.trim());
    setEditingProvider(null);
    setEditingKey("");
    fetchSettings().then(setSettings);
    fetchAuthStatus().then(setAuthStatus);
  };

  const handleRemoveKey = async (provider: string) => {
    await deleteApiKey(provider);
    fetchSettings().then(setSettings);
    fetchAuthStatus().then(setAuthStatus);
  };

  const isProviderAuthenticated = (providerId: string): boolean => {
    if (!settings) return false;
    return settings.authenticated_providers?.includes(providerId) || false;
  };

  const handleOAuthSignIn = async (provider: string) => {
    setOauthLoading(provider);
    try {
      const result = await startOAuth(provider);
      if (result.url) {
        // Open OAuth popup
        const popup = window.open(result.url, 'oauth_popup', 'width=500,height=700,left=200,top=100');

        // Listen for the OAuth completion message from the popup
        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === 'oauth_complete') {
            window.removeEventListener('message', handleMessage);
            setOauthLoading(null);
            // Refresh auth status
            fetchSettings().then(setSettings);
            fetchAuthStatus().then(setAuthStatus);
          }
        };
        window.addEventListener('message', handleMessage);

        // Also poll in case the message doesn't arrive (popup blockers, etc.)
        const pollInterval = setInterval(() => {
          if (popup?.closed) {
            clearInterval(pollInterval);
            window.removeEventListener('message', handleMessage);
            setOauthLoading(null);
            fetchSettings().then(setSettings);
            fetchAuthStatus().then(setAuthStatus);
          }
        }, 1000);
      }
    } catch {
      setOauthLoading(null);
    }
  };

  const quickActions = [
    "Create a Python project",
    "Fix a bug in my code",
    "Search the web",
    "Explain this codebase",
  ];

  // ── Render ──────────────────────────────────────────────────────
  return (
    <div className="app-layout">
      <div className={`sidebar-overlay ${sidebarOpen ? "visible" : ""}`} onClick={() => setSidebarOpen(false)} />

      {/* ═══ SIDEBAR ═══ */}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="logo-icon">N</div>
            <span>NexCode</span>
          </div>
          <button className="new-chat-btn" onClick={handleNewChat}>+ New</button>
        </div>

        <div className="conversation-list">
          {conversations.length === 0 ? (
            <div style={{ padding: "20px 14px", color: "var(--text-muted)", fontSize: "13px" }}>
              No conversations yet.<br />Start chatting to begin!
            </div>
          ) : (
            conversations.map(conv => (
              <div key={conv.id} className={`conversation-item ${conv.id === sessionId ? "active" : ""}`}>
                <span className="conv-icon">💬</span>
                <span className="conv-title">{conv.title}</span>
                <button className="conv-delete" onClick={(e) => { e.stopPropagation(); handleDeleteConv(conv.id); }} title="Delete">✕</button>
              </div>
            ))
          )}
        </div>

        <div className="sidebar-footer">
          <div className="model-badge" onClick={() => setShowModelSelector(true)}>
            <span className="dot" />
            <span style={{ flex: 1 }}>{currentModel.split("/").pop()}</span>
            <span style={{ fontSize: "10px", opacity: 0.5 }}>▼</span>
          </div>
          <button className="settings-btn" onClick={() => { setShowSettings(true); setSettingsTab("auth"); fetchSettings().then(setSettings); }}>
            🔑 Authentication
          </button>
          <button className="settings-btn" onClick={() => { setShowSettings(true); setSettingsTab("general"); fetchSettings().then(setSettings); }}>
            ⚙️ Settings
          </button>
        </div>
      </aside>

      {/* ═══ MAIN CHAT ═══ */}
      <main className="main-content">
        <header className="chat-header">
          <button className="hamburger-btn" onClick={() => setSidebarOpen(true)}>☰</button>
          <h1 className="chat-header-title">NexCode</h1>
          <button className="header-model-btn" onClick={() => setShowModelSelector(true)}>
            <span className="dot" style={{ width: 6, height: 6 }} />
            {currentProvider}/{currentModel.split("/").pop()}
            <span style={{ fontSize: "10px", opacity: 0.5 }}>▼</span>
          </button>
        </header>

        <div className="chat-messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              <div className="empty-logo">N</div>
              <h2 className="empty-title">Welcome to NexCode</h2>
              <p className="empty-subtitle">
                Your AI coding assistant. Ask me to write code, fix bugs,
                search the web, or manage your project.
              </p>
              <div className="quick-actions">
                {quickActions.map(a => (
                  <button key={a} className="quick-action-btn" onClick={() => { setInput(a); inputRef.current?.focus(); }}>{a}</button>
                ))}
              </div>
            </div>
          ) : (
            <div className="message-container">
              {messages.map(msg => (
                <div key={msg.id} className="message">
                  <div className={`message-avatar ${msg.role}`}>{msg.role === "user" ? "U" : "N"}</div>
                  <div className="message-body">
                    <div className="sender-name">{msg.role === "user" ? "You" : "NexCode"}</div>
                    {msg.toolCalls?.map(tc => <ToolCallPanel key={tc.id} toolCall={tc} />)}
                    {msg.content && <div className="content"><FormattedContent content={msg.content} /></div>}
                  </div>
                </div>
              ))}
              {isStreaming && (
                <div className="thinking-indicator">
                  <div className="thinking-dots"><span /><span /><span /></div>Thinking...
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <textarea ref={inputRef} className="chat-input" value={input}
              onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown}
              placeholder="Ask NexCode anything..." rows={1} disabled={isStreaming} />
            <button className="send-btn" onClick={sendMessage} disabled={!input.trim() || isStreaming}>↑</button>
          </div>
          <div className="input-footer">NexCode can make mistakes. Verify important code.</div>
        </div>
      </main>

      {/* ═══ MODEL SELECTOR MODAL ═══ */}
      {showModelSelector && (
        <div className="modal-overlay" onClick={() => setShowModelSelector(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Select Model</h2>
              <button className="modal-close" onClick={() => setShowModelSelector(false)}>✕</button>
            </div>
            <div className="modal-body">
              {providers.map(p => {
                const meta = PROVIDER_META[p.id];
                const isAuth = isProviderAuthenticated(p.id);
                return (
                  <div key={p.id} className="provider-group">
                    <div className="provider-header">
                      <span className="provider-name">{meta?.icon || "🔹"} {p.name}</span>
                      <span className="provider-desc">{p.description}</span>
                      {isAuth && <span className="auth-badge auth-active">✓ Active</span>}
                      {!isAuth && p.id !== "ollama" && (
                        <span className="auth-badge auth-inactive" onClick={() => { setShowModelSelector(false); setShowSettings(true); setSettingsTab("auth"); }}>
                          🔑 Add Key
                        </span>
                      )}
                    </div>
                    <div className="model-list">
                      {p.models.map(m => (
                        <button key={m}
                          className={`model-item ${currentProvider === p.id && currentModel === m ? "active" : ""} ${!isAuth && p.id !== "openrouter" ? "disabled-model" : ""}`}
                          onClick={() => handleSwitchModel(p.id, m)}>
                          <span className="model-name">{m}</span>
                          {currentProvider === p.id && currentModel === m && <span className="model-active-badge">Active</span>}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ═══ SETTINGS / AUTH MODAL ═══ */}
      {showSettings && settings && (
        <div className="modal-overlay" onClick={() => setShowSettings(false)}>
          <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{settingsTab === "auth" ? "🔑 Authentication" : settingsTab === "tools" ? "🔧 Tools" : "⚙️ Settings"}</h2>
              <button className="modal-close" onClick={() => setShowSettings(false)}>✕</button>
            </div>

            <div className="tabs">
              {(["auth", "general", "tools"] as const).map(t => (
                <button key={t} className={`tab ${settingsTab === t ? "active" : ""}`}
                  onClick={() => setSettingsTab(t)}>
                  {t === "auth" ? "🔑 Providers" : t === "general" ? "⚙️ General" : "🔧 Tools"}
                </button>
              ))}
            </div>

            <div className="modal-body">
              {/* ── AUTH TAB ─────────────────────────────────── */}
              {settingsTab === "auth" && (
                <div className="auth-section">
                  <p className="setting-hint" style={{ marginBottom: 16 }}>
                    Sign in with your account or add API keys to unlock AI providers. Use your existing subscriptions directly!
                  </p>

                  {Object.entries(PROVIDER_META).map(([pid, meta]) => {
                    const isAuth = isProviderAuthenticated(pid);
                    const maskedKey = settings.api_keys?.[pid] || "";
                    const isEditing = editingProvider === pid;

                    return (
                      <div key={pid} className={`auth-card ${isAuth ? "authenticated" : ""}`}>
                        <div className="auth-card-header">
                          <div className="auth-card-icon" style={{ background: meta.color }}>
                            {meta.icon}
                          </div>
                          <div className="auth-card-info">
                            <div className="auth-card-name">
                              {meta.name}
                              {isAuth && <span className="auth-status-dot active" />}
                              {!isAuth && <span className="auth-status-dot" />}
                            </div>
                            <div className="auth-card-desc">{meta.description}</div>
                            <div className="auth-card-models">Models: {meta.models}</div>
                          </div>
                        </div>

                        {isAuth && !isEditing && (
                          <div className="auth-card-actions">
                            <span className="auth-key-masked">
                              {authStatus[pid]?.auth_type === 'oauth' ? '🔗 Signed in via OAuth' : `🔒 ${maskedKey || 'Connected'}`}
                            </span>
                            <button className="auth-btn auth-btn-danger" onClick={() => handleRemoveKey(pid)}>
                              {authStatus[pid]?.auth_type === 'oauth' ? 'Sign Out' : 'Remove'}
                            </button>
                          </div>
                        )}

                        {!isAuth && !isEditing && (
                          <div className="auth-card-actions">
                            {meta.supportsOAuth && (
                              <button
                                className="auth-btn auth-btn-oauth"
                                onClick={() => handleOAuthSignIn(pid)}
                                disabled={oauthLoading === pid}
                              >
                                {oauthLoading === pid ? (
                                  <>⏳ Signing in...</>
                                ) : (
                                  <>{pid === 'google' ? '🔷' : '🐙'} Sign in with {meta.name}</>
                                )}
                              </button>
                            )}
                            <button className="auth-btn auth-btn-primary" onClick={() => { setEditingProvider(pid); setEditingKey(""); }}>
                              🔑 Add API Key
                            </button>
                            <a className="auth-btn auth-btn-link" href={meta.signupUrl} target="_blank" rel="noopener noreferrer">
                              Get Key ↗
                            </a>
                          </div>
                        )}

                        {isEditing && (
                          <div className="auth-card-form">
                            <div className="auth-form-hint">
                              Paste your {meta.name} API key below.
                              <a href={meta.signupUrl} target="_blank" rel="noopener noreferrer"> Get a key ↗</a>
                            </div>
                            <div className="auth-form-row">
                              <input
                                type="password"
                                className="auth-form-input"
                                placeholder={`${meta.keyPrefix}...`}
                                value={editingKey}
                                onChange={e => setEditingKey(e.target.value)}
                                onKeyDown={e => { if (e.key === "Enter") handleAddKey(pid); }}
                                autoFocus
                              />
                              <button className="auth-btn auth-btn-primary" onClick={() => handleAddKey(pid)} disabled={!editingKey.trim()}>
                                Save
                              </button>
                              <button className="auth-btn auth-btn-ghost" onClick={() => { setEditingProvider(null); setEditingKey(""); }}>
                                Cancel
                              </button>
                            </div>
                            <div className="auth-form-env">
                              Or set env: <code>{meta.envVar}</code>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {/* Ollama section */}
                  <div className={`auth-card ${isProviderAuthenticated("ollama") ? "authenticated" : ""}`}>
                    <div className="auth-card-header">
                      <div className="auth-card-icon" style={{ background: "#22c55e" }}>🦙</div>
                      <div className="auth-card-info">
                        <div className="auth-card-name">
                          Ollama (Local)
                          {isProviderAuthenticated("ollama") ? <span className="auth-status-dot active" /> : <span className="auth-status-dot" />}
                        </div>
                        <div className="auth-card-desc">Run models locally, completely offline. No API key needed.</div>
                        <div className="auth-card-models">Models: Llama 3.1, CodeLlama, Mistral, Qwen</div>
                      </div>
                    </div>
                    <div className="auth-card-actions">
                      <a className="auth-btn auth-btn-link" href="https://ollama.ai" target="_blank" rel="noopener noreferrer">
                        Install Ollama ↗
                      </a>
                    </div>
                  </div>
                </div>
              )}

              {/* ── GENERAL TAB ──────────────────────────────── */}
              {settingsTab === "general" && (
                <div className="settings-section">
                  <label className="setting-label">
                    Max Tokens
                    <input type="number" className="setting-input" value={settings.max_tokens}
                      onChange={e => setSettings({ ...settings, max_tokens: Number(e.target.value) })} />
                  </label>
                  <label className="setting-label">
                    Permission Mode
                    <select className="setting-input" value={settings.permission_mode}
                      onChange={e => setSettings({ ...settings, permission_mode: e.target.value })}>
                      <option value="ask">Ask (default)</option>
                      <option value="auto">Auto</option>
                      <option value="strict">Strict</option>
                      <option value="yolo">YOLO (no prompts)</option>
                    </select>
                  </label>
                  <label className="setting-label">
                    Theme
                    <select className="setting-input" value={settings.theme}
                      onChange={e => setSettings({ ...settings, theme: e.target.value })}>
                      <option value="dark">Dark</option>
                      <option value="light">Light</option>
                    </select>
                  </label>
                  <button className="save-btn" onClick={handleSaveSettings}>Save Settings</button>
                </div>
              )}

              {/* ── TOOLS TAB ────────────────────────────────── */}
              {settingsTab === "tools" && (
                <div className="settings-section">
                  <p className="setting-hint">NexCode has 36+ registered tools for file operations, git, web search, and more.</p>
                  <div className="tools-grid">
                    {["read_file", "write_file", "edit_file", "create_file", "delete_file",
                      "list_directory", "find_files", "search_text", "run_command",
                      "git_status", "git_commit", "git_diff", "git_log",
                      "web_search", "fetch_page", "deep_research"
                    ].map(t => (
                      <div key={t} className="tool-chip">{t}</div>
                    ))}
                    <div className="tool-chip" style={{ opacity: 0.5 }}>+ 20 more...</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   Sub-components
   ═══════════════════════════════════════════════════════════════════ */

function ToolCallPanel({ toolCall }: { toolCall: ToolCall }) {
  const [isOpen, setIsOpen] = useState(false);
  const label = toolCall.status === "running" ? "Running..." : toolCall.status === "success" ? "Done" : "Failed";
  return (
    <div className="tool-panel">
      <div className="tool-panel-header" onClick={() => setIsOpen(!isOpen)}>
        <span className="tool-panel-icon">🔧</span>
        <span className="tool-panel-name">{toolCall.tool}</span>
        <span className={`tool-panel-status ${toolCall.status}`}>{label}</span>
        <span className={`tool-panel-chevron ${isOpen ? "open" : ""}`}>▼</span>
      </div>
      {isOpen && (
        <div className="tool-panel-body">
          <div style={{ marginBottom: 8, color: "var(--accent-light)" }}>Args: {JSON.stringify(toolCall.arguments, null, 2)}</div>
          {toolCall.result && <div>Result: {toolCall.result}</div>}
        </div>
      )}
    </div>
  );
}

function FormattedContent({ content }: { content: string }) {
  const parts = content.split(/(```[\s\S]*?```)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          const lines = part.slice(3, -3).split("\n");
          const lang = lines[0]?.trim() || "code";
          const code = lines.slice(1).join("\n");
          return (
            <div key={i} className="code-block">
              <div className="code-block-header">
                <span>{lang}</span>
                <button className="code-block-copy" onClick={() => navigator.clipboard.writeText(code)}>Copy</button>
              </div>
              <pre>{code}</pre>
            </div>
          );
        }
        const html = part
          .replace(/`([^`]+)`/g, '<code style="background:var(--bg-tertiary);padding:2px 6px;border-radius:4px;font-family:JetBrains Mono,monospace;font-size:12px">$1</code>')
          .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
          .replace(/\n/g, "<br />");
        return <span key={i} dangerouslySetInnerHTML={{ __html: html }} />;
      })}
    </>
  );
}
