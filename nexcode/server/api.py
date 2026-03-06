"""
NexCode Web API Server
~~~~~~~~~~~~~~~~~~~~~~~~

FastAPI application that exposes the NexCode engine via REST + WebSocket
endpoints for browser-based access.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nexcode.server.session import WebSessionManager


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ModelSwitchRequest(BaseModel):
    provider: str
    model: str


class NewSessionRequest(BaseModel):
    title: str = "New Chat"


class UpdateSettingsRequest(BaseModel):
    default_provider: str | None = None
    default_model: str | None = None
    max_tokens: int | None = None
    theme: str | None = None
    permission_mode: str | None = None


class ApiKeyRequest(BaseModel):
    provider: str
    key: str


class RenameSessionRequest(BaseModel):
    title: str


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="NexCode",
        description="AI-Powered Coding Assistant — Web Interface",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    manager = WebSessionManager()

    # ══════════════════════════════════════════════════════════════════
    # HEALTH
    # ══════════════════════════════════════════════════════════════════

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "1.0.0"}

    # ══════════════════════════════════════════════════════════════════
    # CHAT — REST + WebSocket
    # ══════════════════════════════════════════════════════════════════

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        session_id = req.session_id
        if not session_id:
            session = manager.create_session()
            session_id = session.id

        result = await manager.process_message(session_id, req.message)
        result["session_id"] = session_id
        return result

    @app.websocket("/api/chat/stream")
    async def chat_stream(ws: WebSocket):
        await ws.accept()
        try:
            while True:
                data = await ws.receive_text()
                msg = json.loads(data)
                user_input = msg.get("message", "")
                session_id = msg.get("session_id")

                if not session_id:
                    session = manager.create_session()
                    session_id = session.id
                    await ws.send_json({
                        "type": "session_created",
                        "session_id": session_id,
                    })

                session = manager.get_session(session_id)
                if not session:
                    await ws.send_json({
                        "type": "error",
                        "message": "Session not found",
                    })
                    continue

                session.history.add_user(user_input)
                session.message_count += 1
                tools = manager.tool_registry.get_api_schemas()
                final_content = ""

                for _ in range(10):
                    response = await manager.provider.chat(
                        messages=session.history.get_api_messages(),
                        tools=tools,
                    )

                    if response.content:
                        session.history.add_assistant(response.content)
                        final_content = response.content
                        await ws.send_json({
                            "type": "token",
                            "content": response.content,
                        })

                    if not response.tool_calls:
                        break

                    for call in response.tool_calls:
                        session.history.add_tool_call(
                            call.id, call.name, call.arguments
                        )
                        await ws.send_json({
                            "type": "tool_start",
                            "tool": call.name,
                            "arguments": call.arguments,
                        })

                        result = await manager.tool_registry.execute(
                            tool_name=call.name,
                            parameters=call.arguments,
                        )
                        session.history.add_tool_result(
                            call.id, result.output, not result.success
                        )
                        await ws.send_json({
                            "type": "tool_end",
                            "tool": call.name,
                            "result": result.output[:2000],
                            "success": result.success,
                        })

                if session.message_count == 1:
                    session.title = user_input[:60] + (
                        "..." if len(user_input) > 60 else ""
                    )

                session.updated_at = datetime.now(timezone.utc)
                session.message_count += 1

                await ws.send_json({
                    "type": "done",
                    "content": final_content,
                    "session_id": session_id,
                    "model": manager.provider.current_model,
                    "provider": manager.provider.current_provider,
                })

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            try:
                await ws.send_json({"type": "error", "message": str(exc)})
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════
    # CONVERSATIONS
    # ══════════════════════════════════════════════════════════════════

    @app.get("/api/conversations")
    async def list_conversations():
        return manager.list_sessions()

    @app.post("/api/conversations")
    async def create_conversation(req: NewSessionRequest):
        session = manager.create_session(title=req.title)
        return session.to_dict()

    @app.delete("/api/conversations/{session_id}")
    async def delete_conversation(session_id: str):
        if manager.delete_session(session_id):
            return {"ok": True}
        return JSONResponse(status_code=404, content={"error": "Not found"})

    @app.patch("/api/conversations/{session_id}")
    async def rename_conversation(session_id: str, req: RenameSessionRequest):
        session = manager.get_session(session_id)
        if not session:
            return JSONResponse(status_code=404, content={"error": "Not found"})
        session.title = req.title
        return session.to_dict()

    # ══════════════════════════════════════════════════════════════════
    # MODELS & PROVIDERS
    # ══════════════════════════════════════════════════════════════════

    @app.get("/api/models")
    async def list_models():
        return {
            "current_model": manager.provider.current_model,
            "current_provider": manager.provider.current_provider,
            "available": manager.provider.list_all_available_models(),
            "all_providers": _get_all_providers(),
        }

    @app.post("/api/models/switch")
    async def switch_model(req: ModelSwitchRequest):
        try:
            manager.provider._current_provider = req.provider
            manager.provider._current_model = req.model
            manager.provider._configure_litellm()

            # Persist to config.
            from nexcode.config import save_config
            manager.config.default_provider = req.provider
            manager.config.default_model = req.model
            save_config(manager.config)

            return {
                "ok": True,
                "model": req.model,
                "provider": req.provider,
            }
        except Exception as exc:
            return JSONResponse(
                status_code=400, content={"error": str(exc)}
            )

    @app.get("/api/providers")
    async def list_providers():
        return _get_all_providers()

    # ══════════════════════════════════════════════════════════════════
    # TOOLS
    # ══════════════════════════════════════════════════════════════════

    @app.get("/api/tools")
    async def list_tools():
        tools = manager.tool_registry._tools
        return [
            {
                "name": t.name,
                "description": t.description,
                "is_read_only": getattr(t, "is_read_only", False),
            }
            for t in tools.values()
        ]

    # ══════════════════════════════════════════════════════════════════
    # SETTINGS
    # ══════════════════════════════════════════════════════════════════

    @app.get("/api/settings")
    async def get_settings():
        return {
            "default_provider": manager.config.default_provider,
            "default_model": manager.config.default_model,
            "max_tokens": manager.config.max_tokens,
            "theme": manager.config.theme,
            "permission_mode": manager.config.permission_mode,
            "api_keys": {
                k: f"...{v[-6:]}" if v else ""
                for k, v in manager.config.api_keys.items()
            },
            "authenticated_providers": manager.auth.list_authenticated_providers(),
        }

    @app.put("/api/settings")
    async def update_settings(req: UpdateSettingsRequest):
        from nexcode.config import save_config

        if req.default_provider is not None:
            manager.config.default_provider = req.default_provider
            manager.provider._current_provider = req.default_provider
        if req.default_model is not None:
            manager.config.default_model = req.default_model
            manager.provider._current_model = req.default_model
        if req.max_tokens is not None:
            manager.config.max_tokens = req.max_tokens
        if req.theme is not None:
            manager.config.theme = req.theme
        if req.permission_mode is not None:
            manager.config.permission_mode = req.permission_mode

        manager.provider._configure_litellm()
        save_config(manager.config)

        return {"ok": True, "message": "Settings saved"}

    @app.post("/api/settings/apikey")
    async def set_api_key(req: ApiKeyRequest):
        import os
        from nexcode.config import save_config

        manager.config.api_keys[req.provider] = req.key
        manager.auth.set_api_key(req.provider, req.key)

        # Set in environment for LiteLLM.
        from nexcode.ai.auth import ENV_KEY_MAP
        env_var = ENV_KEY_MAP.get(req.provider)
        if env_var:
            os.environ[env_var] = req.key

        manager.provider._configure_litellm()
        save_config(manager.config)

        return {"ok": True, "provider": req.provider}

    @app.delete("/api/settings/apikey/{provider}")
    async def delete_api_key(provider: str):
        import os
        from nexcode.config import save_config

        if provider in manager.config.api_keys:
            del manager.config.api_keys[provider]

        from nexcode.ai.auth import ENV_KEY_MAP
        env_var = ENV_KEY_MAP.get(provider)
        if env_var and env_var in os.environ:
            del os.environ[env_var]

        save_config(manager.config)
        return {"ok": True}

    # ══════════════════════════════════════════════════════════════════
    # OAUTH — Sign in with Google / GitHub
    # ══════════════════════════════════════════════════════════════════

    @app.get("/api/auth/status")
    async def auth_status():
        """Return auth status for every provider."""
        from nexcode.ai.auth import API_KEY_PROVIDERS

        providers_info = {}
        for pid in ["openrouter", "anthropic", "google", "openai",
                     "groq", "deepseek", "mistral", "github", "ollama"]:
            is_auth = manager.auth.is_authenticated(pid)
            auth_type = "none"
            if pid == "ollama":
                auth_type = "local"
            elif pid in ("google", "github"):
                # Check if authenticated via OAuth or API key
                if pid in manager.auth._oauth_tokens:
                    auth_type = "oauth"
                elif manager.auth.get_api_key(pid):
                    auth_type = "api_key"
            elif manager.auth.get_api_key(pid):
                auth_type = "api_key"

            providers_info[pid] = {
                "authenticated": is_auth,
                "auth_type": auth_type,
                "supports_oauth": pid in ("google", "github"),
                "supports_api_key": pid in API_KEY_PROVIDERS,
            }

        return providers_info

    @app.get("/api/auth/{provider}/start")
    async def oauth_start(provider: str):
        """Start an OAuth flow. Returns the URL to redirect the user to."""
        import secrets
        from urllib.parse import urlencode

        provider = provider.lower()

        if provider == "google":
            from nexcode.ai.auth import (
                GOOGLE_CLIENT_ID, GOOGLE_AUTH_URI,
                GOOGLE_SCOPES,
            )

            # Use our own callback endpoint (not localhost:8484)
            redirect_uri = "http://localhost:8000/api/auth/google/callback"
            state = secrets.token_urlsafe(32)

            # Store state for CSRF verification
            app.state.oauth_state = state

            params = {
                "client_id": GOOGLE_CLIENT_ID,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(GOOGLE_SCOPES),
                "state": state,
                "access_type": "offline",
                "prompt": "consent",
            }
            auth_url = f"{GOOGLE_AUTH_URI}?{urlencode(params)}"

            return {"url": auth_url, "provider": "google"}

        elif provider == "github":
            from nexcode.ai.auth import (
                GITHUB_CLIENT_ID, GITHUB_DEVICE_CODE_URL, GITHUB_SCOPES,
            )
            import httpx

            # GitHub uses Device Flow — request device + user codes
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    GITHUB_DEVICE_CODE_URL,
                    data={"client_id": GITHUB_CLIENT_ID, "scope": GITHUB_SCOPES},
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()

            return {
                "provider": "github",
                "flow": "device",
                "user_code": data["user_code"],
                "verification_uri": data["verification_uri"],
                "device_code": data["device_code"],
                "interval": data.get("interval", 5),
            }

        return JSONResponse(
            status_code=400,
            content={"error": f"OAuth not supported for {provider}"},
        )

    @app.get("/api/auth/google/callback")
    async def google_oauth_callback(code: str = "", state: str = "", error: str = ""):
        """Handle the Google OAuth redirect — returns HTML that closes the popup."""
        from fastapi.responses import HTMLResponse

        if error:
            return HTMLResponse(f"""
            <html><body style="background:#0a0a0f;color:#fff;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
            <div style="text-align:center"><h2>❌ Authentication Failed</h2><p>{error}</p>
            <script>setTimeout(()=>window.close(),3000)</script></div></body></html>
            """)

        # Verify state
        expected_state = getattr(app.state, "oauth_state", None)
        if state != expected_state:
            return HTMLResponse("""
            <html><body style="background:#0a0a0f;color:#fff;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
            <div style="text-align:center"><h2>❌ State Mismatch</h2><p>Possible security issue. Try again.</p>
            <script>setTimeout(()=>window.close(),3000)</script></div></body></html>
            """)

        # Exchange code for tokens
        import time
        import httpx
        from nexcode.ai.auth import (
            GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_TOKEN_URI,
            OAuthToken,
        )

        redirect_uri = "http://localhost:8000/api/auth/google/callback"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    GOOGLE_TOKEN_URI,
                    data={
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            return HTMLResponse(f"""
            <html><body style="background:#0a0a0f;color:#fff;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
            <div style="text-align:center"><h2>❌ Token Exchange Failed</h2><p>{exc}</p>
            <script>setTimeout(()=>window.close(),3000)</script></div></body></html>
            """)

        # Store the token
        token = OAuthToken(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=time.time() + data.get("expires_in", 3600),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope", ""),
        )
        manager.auth._oauth_tokens["google"] = token
        manager.auth._save_token("google", token)

        # Also set in environment so LiteLLM can see it
        import os
        os.environ["GOOGLE_API_KEY"] = data["access_token"]
        manager.provider._configure_litellm()

        return HTMLResponse("""
        <html><body style="background:#0a0a0f;color:#fff;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
        <div style="text-align:center">
            <div style="width:64px;height:64px;background:linear-gradient(135deg,#4285f4,#34a853);border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:28px;margin:0 auto 16px">✓</div>
            <h2 style="color:#00d2a0;margin-bottom:8px">Signed in with Google!</h2>
            <p style="color:#a0a0b8">You can close this tab and return to NexCode.</p>
            <p style="color:#6b6b80;font-size:12px;margin-top:16px">Gemini models are now available.</p>
            <script>
                if (window.opener) { window.opener.postMessage({type:'oauth_complete',provider:'google'}, '*'); }
                setTimeout(() => window.close(), 2000);
            </script>
        </div></body></html>
        """)

    @app.post("/api/auth/github/poll")
    async def github_oauth_poll(device_code: str = ""):
        """Poll GitHub for the device flow token."""
        import httpx
        from nexcode.ai.auth import GITHUB_CLIENT_ID, GITHUB_TOKEN_URL, OAuthToken

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GITHUB_TOKEN_URL,
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers={"Accept": "application/json"},
            )
            result = resp.json()

        if "access_token" in result:
            token = OAuthToken(
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token"),
                token_type=result.get("token_type", "bearer"),
                scope=result.get("scope", ""),
            )
            manager.auth._oauth_tokens["github"] = token
            manager.auth._save_token("github", token)
            return {"ok": True, "provider": "github"}

        return {
            "ok": False,
            "status": result.get("error", "pending"),
        }

    # ── Serve frontend ──────────────────────────────────────────────

    frontend_dir = Path(__file__).parent.parent.parent / "web" / "out"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True))

    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_all_providers() -> list[dict[str, Any]]:
    """Return a static list of all supported providers with their models."""
    return [
        {
            "id": "openrouter",
            "name": "OpenRouter",
            "description": "186+ models, free tier available",
            "models": [
                "moonshotai/kimi-k2.5",
                "google/gemini-2.0-flash-exp:free",
                "deepseek/deepseek-chat-v3-0324:free",
                "meta-llama/llama-3.3-70b-instruct:free",
                "qwen/qwen3-235b-a22b:free",
                "mistralai/mistral-small-3.1-24b-instruct:free",
            ],
        },
        {
            "id": "anthropic",
            "name": "Anthropic",
            "description": "Claude models — best for coding",
            "models": [
                "claude-opus-4-6",
                "claude-sonnet-4-20250514",
                "claude-3-5-haiku-20241022",
            ],
        },
        {
            "id": "openai",
            "name": "OpenAI",
            "description": "GPT-4o and o1 models",
            "models": [
                "gpt-4o",
                "gpt-4o-mini",
                "o1-preview",
                "o1-mini",
            ],
        },
        {
            "id": "google",
            "name": "Google",
            "description": "Gemini models — free with API key",
            "models": [
                "gemini-2.0-flash",
                "gemini-2.5-pro-preview-06-05",
                "gemini-2.5-flash-preview-05-20",
            ],
        },
        {
            "id": "groq",
            "name": "Groq",
            "description": "Ultra-fast inference",
            "models": [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
            ],
        },
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "description": "DeepSeek coding models",
            "models": [
                "deepseek-chat",
                "deepseek-coder",
            ],
        },
        {
            "id": "ollama",
            "name": "Ollama (Local)",
            "description": "Run models locally — fully offline",
            "models": [
                "llama3.1",
                "codellama",
                "mistral",
                "qwen2.5-coder",
            ],
        },
    ]
