/**
 * NexCode WebSocket & REST API Client
 */

export type MessageRole = "user" | "assistant";

export interface ToolCall {
    id: string;
    tool: string;
    arguments: Record<string, unknown>;
    result?: string;
    success?: boolean;
    status: "running" | "success" | "error";
}

export interface ChatMessage {
    id: string;
    role: MessageRole;
    content: string;
    toolCalls?: ToolCall[];
    timestamp: Date;
}

export interface Conversation {
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}

export interface ProviderInfo {
    id: string;
    name: string;
    description: string;
    models: string[];
}

export interface AppSettings {
    default_provider: string;
    default_model: string;
    max_tokens: number;
    theme: string;
    permission_mode: string;
    api_keys: Record<string, string>;
    authenticated_providers: string[];
}

// ── Base ──────────────────────────────────────────────────────────

const API_BASE = typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://localhost:8000";

async function api(path: string, options?: RequestInit) {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    return res.json();
}

// ── Conversations ─────────────────────────────────────────────────

export const fetchConversations = (): Promise<Conversation[]> => api("/api/conversations");
export const createConversation = (title = "New Chat") =>
    api("/api/conversations", { method: "POST", body: JSON.stringify({ title }) });
export const deleteConversation = (id: string) =>
    api(`/api/conversations/${id}`, { method: "DELETE" });
export const renameConversation = (id: string, title: string) =>
    api(`/api/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ title }) });

// ── Models & Providers ────────────────────────────────────────────

export const fetchModels = () => api("/api/models");
export const fetchProviders = (): Promise<ProviderInfo[]> => api("/api/providers");
export const switchModel = (provider: string, model: string) =>
    api("/api/models/switch", { method: "POST", body: JSON.stringify({ provider, model }) });

// ── Settings ──────────────────────────────────────────────────────

export const fetchSettings = (): Promise<AppSettings> => api("/api/settings");
export const updateSettings = (settings: Partial<AppSettings>) =>
    api("/api/settings", { method: "PUT", body: JSON.stringify(settings) });
export const setApiKey = (provider: string, key: string) =>
    api("/api/settings/apikey", { method: "POST", body: JSON.stringify({ provider, key }) });
export const deleteApiKey = (provider: string) =>
    api(`/api/settings/apikey/${provider}`, { method: "DELETE" });

// ── Tools ─────────────────────────────────────────────────────────

export const fetchTools = () => api("/api/tools");

// ── Auth / OAuth ──────────────────────────────────────────────────

export interface AuthProviderStatus {
    authenticated: boolean;
    auth_type: "none" | "api_key" | "oauth" | "local";
    supports_oauth: boolean;
    supports_api_key: boolean;
}

export const fetchAuthStatus = (): Promise<Record<string, AuthProviderStatus>> =>
    api("/api/auth/status");

export const startOAuth = (provider: string): Promise<{
    url?: string;
    provider: string;
    flow?: string;
    user_code?: string;
    verification_uri?: string;
    device_code?: string;
    interval?: number;
}> => api(`/api/auth/${provider}/start`);

export const pollGithubAuth = (deviceCode: string) =>
    api("/api/auth/github/poll", { method: "POST", body: JSON.stringify({ device_code: deviceCode }) });

// ── WebSocket streaming ───────────────────────────────────────────

export interface StreamCallbacks {
    onSessionCreated?: (sessionId: string) => void;
    onToken?: (content: string) => void;
    onToolStart?: (tool: string, args: Record<string, unknown>) => void;
    onToolEnd?: (tool: string, result: string, success: boolean) => void;
    onDone?: (content: string, sessionId: string, model: string, provider: string) => void;
    onError?: (message: string) => void;
}

export function sendStreamingMessage(
    message: string,
    sessionId: string | null,
    callbacks: StreamCallbacks
): WebSocket {
    const wsBase = API_BASE.replace(/^http/, "ws");
    const ws = new WebSocket(`${wsBase}/api/chat/stream`);

    ws.onopen = () => {
        ws.send(JSON.stringify({ message, session_id: sessionId }));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        switch (data.type) {
            case "session_created": callbacks.onSessionCreated?.(data.session_id); break;
            case "token": callbacks.onToken?.(data.content); break;
            case "tool_start": callbacks.onToolStart?.(data.tool, data.arguments); break;
            case "tool_end": callbacks.onToolEnd?.(data.tool, data.result, data.success); break;
            case "done": callbacks.onDone?.(data.content, data.session_id, data.model, data.provider); ws.close(); break;
            case "error": callbacks.onError?.(data.message); ws.close(); break;
        }
    };

    ws.onerror = () => {
        callbacks.onError?.("Connection failed. Is the NexCode server running?");
    };

    return ws;
}
