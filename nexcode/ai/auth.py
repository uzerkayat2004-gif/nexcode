"""
NexCode Authentication Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles three authentication strategies:
  1. API Key — reads from config or environment variables
  2. OAuth — browser-based Google OAuth 2.0 and GitHub Device Flow
  3. No Auth — local Ollama auto-detection

Tokens are persisted to ~/.nexcode/ and auto-refreshed transparently.
"""

from __future__ import annotations

import json
import os
import secrets
import time
import webbrowser
from dataclasses import dataclass
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from rich.console import Console
from rich.table import Table
from rich.text import Text

from nexcode.ai.models import MODEL_REGISTRY, list_models_for_provider


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NEXCODE_DIR = Path.home() / ".nexcode"

# Provider → environment variable name mapping.
ENV_KEY_MAP: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "google": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "minimax": "MINIMAX_API_KEY",
}

# Providers that use simple API key auth.
API_KEY_PROVIDERS: set[str] = set(ENV_KEY_MAP.keys())

# Providers that use OAuth.
OAUTH_PROVIDERS: set[str] = {"google", "github"}

# ---------- Google OAuth 2.0 ----------
# NOTE: Replace these with your own registered OAuth app credentials
# for production use.  These are placeholder/development values.
GOOGLE_CLIENT_ID = "nexcode-dev.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "GOCSPX-placeholder-secret"
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/generative-language",
    "https://www.googleapis.com/auth/cloud-platform",
]
GOOGLE_REDIRECT_PORT = 8484
GOOGLE_REDIRECT_URI = f"http://localhost:{GOOGLE_REDIRECT_PORT}/callback"

# ---------- GitHub Device Flow ----------
# NOTE: Replace with your own GitHub OAuth App client ID for production.
GITHUB_CLIENT_ID = "Ov23li-placeholder-id"
GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_SCOPES = "read:user copilot"

# ---------- Ollama ----------
OLLAMA_BASE_URL = "http://localhost:11434"


# ---------------------------------------------------------------------------
# Token persistence dataclass
# ---------------------------------------------------------------------------

@dataclass
class OAuthToken:
    """Stored OAuth token with refresh capability."""

    access_token: str
    refresh_token: str | None = None
    expires_at: float = 0.0  # Unix timestamp
    token_type: str = "Bearer"
    scope: str = ""

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired (with 5-minute buffer)."""
        if self.expires_at == 0.0:
            return False  # No expiry info — assume valid.
        return time.time() > (self.expires_at - 300)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OAuthToken:
        """Deserialize from JSON storage."""
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at", 0.0),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope", ""),
        )


# ---------------------------------------------------------------------------
# Internal: Google OAuth callback handler
# ---------------------------------------------------------------------------

class _GoogleCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to capture the Google OAuth redirect."""

    auth_code: str | None = None
    auth_state: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        if code:
            _GoogleCallbackHandler.auth_code = code
            _GoogleCallbackHandler.auth_state = state
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>&#10003; NexCode authenticated with Google!</h2>"
                b"<p>You can close this tab and return to your terminal.</p></body></html>"
            )
        else:
            error = params.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h2>Authentication failed: {error}</h2></body></html>".encode()
            )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Suppress HTTP server logging."""
        pass


# ---------------------------------------------------------------------------
# AuthManager
# ---------------------------------------------------------------------------

class AuthManager:
    """
    Central authentication manager for NexCode.

    Supports API key auth, OAuth flows (Google, GitHub), and
    local Ollama auto-detection.  Tokens are persisted to
    ``~/.nexcode/`` and auto-refreshed when expired.
    """

    def __init__(self, api_keys: dict[str, str] | None = None) -> None:
        self._api_keys: dict[str, str] = api_keys or {}
        self._oauth_tokens: dict[str, OAuthToken] = {}
        self._ollama_models: list[str] = []

        # Ensure the storage directory exists.
        NEXCODE_DIR.mkdir(parents=True, exist_ok=True)

        # Load persisted OAuth tokens.
        self._load_tokens()

    # ── Public API ─────────────────────────────────────────────────────────

    async def login(self, provider: str) -> bool:
        """
        Initiate login for a provider.

        For API key providers, prompts for the key interactively.
        For OAuth providers, starts the appropriate flow.
        For Ollama, checks if the service is running.

        Returns True on success.
        """
        provider = provider.lower()

        if provider == "google":
            return await self._google_oauth_login()
        elif provider == "github":
            return await self._github_device_login()
        elif provider == "ollama":
            return await self._ollama_detect()
        elif provider in API_KEY_PROVIDERS:
            return self._api_key_login(provider)
        else:
            return False

    async def logout(self, provider: str) -> bool:
        """Remove stored credentials for a provider."""
        provider = provider.lower()

        if provider in self._oauth_tokens:
            del self._oauth_tokens[provider]
            token_path = NEXCODE_DIR / f"{provider}_token.json"
            if token_path.exists():
                token_path.unlink()
            return True

        if provider in self._api_keys:
            del self._api_keys[provider]
            return True

        return False

    def get_api_key(self, provider: str) -> str | None:
        """
        Return the API key for a provider.

        Resolution order: environment variable → stored key.
        """
        provider = provider.lower()

        # Environment variable takes precedence.
        env_var = ENV_KEY_MAP.get(provider)
        if env_var:
            env_value = os.environ.get(env_var)
            if env_value:
                return env_value

        return self._api_keys.get(provider)

    def get_oauth_token(self, provider: str) -> str | None:
        """Return the current OAuth access token for a provider, or None."""
        token = self._oauth_tokens.get(provider.lower())
        if token and not token.is_expired:
            return token.access_token
        return None

    def is_authenticated(self, provider: str) -> bool:
        """Check whether a provider is currently authenticated."""
        provider = provider.lower()

        if provider == "ollama":
            return len(self._ollama_models) > 0

        # Check OAuth token.
        if provider in self._oauth_tokens:
            token = self._oauth_tokens[provider]
            return not token.is_expired

        # Check API key.
        return self.get_api_key(provider) is not None

    def list_authenticated_providers(self) -> list[str]:
        """Return a list of all currently authenticated providers."""
        authenticated: list[str] = []
        for provider in list(API_KEY_PROVIDERS) + list(OAUTH_PROVIDERS) + ["ollama"]:
            if self.is_authenticated(provider):
                if provider not in authenticated:
                    authenticated.append(provider)
        return authenticated

    async def refresh_token(self, provider: str) -> bool:
        """
        Attempt to refresh an expired OAuth token.

        Returns True if the token was refreshed successfully.
        """
        provider = provider.lower()
        token = self._oauth_tokens.get(provider)

        if not token or not token.refresh_token:
            return False

        if provider == "google":
            return await self._google_refresh_token(token)
        elif provider == "github":
            # GitHub tokens don't expire in the same way; device tokens
            # are long-lived.  If authentication fails at call time,
            # the user will be prompted to re-login.
            return True

        return False

    def get_effective_credential(self, provider: str) -> str | None:
        """
        Return whatever credential is available for a provider —
        OAuth token preferred, then API key.
        """
        provider = provider.lower()

        # OAuth token first.
        oauth = self.get_oauth_token(provider)
        if oauth:
            return oauth

        # Fall back to API key.
        return self.get_api_key(provider)

    def get_ollama_models(self) -> list[str]:
        """Return cached list of locally detected Ollama models."""
        return list(self._ollama_models)

    # ── Auth status display ────────────────────────────────────────────────

    def show_auth_status(self, console: Console | None = None) -> None:
        """
        Display a Rich table showing authentication status for all providers.
        """
        console = console or Console()

        table = Table(
            title="NexCode — Auth Status",
            title_style="bold white",
            border_style="bright_black",
            show_lines=True,
            padding=(0, 1),
        )
        table.add_column("Provider", style="bold white", min_width=14)
        table.add_column("Status", min_width=12)
        table.add_column("Models", min_width=13)

        # Define display order.
        providers_display = [
            ("anthropic", "Anthropic"),
            ("google", "Google"),
            ("openrouter", "OpenRouter"),
            ("groq", "Groq"),
            ("github", "GitHub"),
            ("ollama", "Ollama"),
            ("openai", "OpenAI"),
            ("mistral", "Mistral"),
            ("deepseek", "DeepSeek"),
            ("minimax", "MiniMax"),
        ]

        for key, display_name in providers_display:
            is_auth = self.is_authenticated(key)

            if is_auth:
                status = Text("✅ Active", style="bold green")
            else:
                status = Text("❌ Not set", style="dim")

            # Model count.
            if key == "ollama":
                count = len(self._ollama_models)
                models_text = f"{count} local" if count > 0 else "—"
            elif key == "openrouter" and is_auth:
                models_text = "186+ models"
            elif is_auth:
                registered = list_models_for_provider(key)
                count = len(registered)
                models_text = f"{count} model{'s' if count != 1 else ''}"
            else:
                models_text = "—"

            table.add_row(display_name, status, models_text)

        console.print()
        console.print(table)
        console.print()

    # ── First-run setup wizard ─────────────────────────────────────────────

    async def first_run_setup(self, console: Console | None = None) -> str | None:
        """
        Interactive first-run setup wizard.

        Returns the chosen default provider, or None if skipped.
        """
        console = console or Console()

        console.print()
        console.print("[bold cyan]Welcome to NexCode![/] Let's get you set up.\n")
        console.print("Choose how to authenticate (you can add more later):\n")
        console.print("  [bold white][1][/] Login with Google [dim](free Gemini access — recommended)[/]")
        console.print("  [bold white][2][/] Enter Anthropic API key")
        console.print("  [bold white][3][/] Enter OpenRouter API key [dim](access 186+ models)[/]")
        console.print("  [bold white][4][/] Use local Ollama [dim](no internet needed)[/]")
        console.print("  [bold white][5][/] Skip for now")
        console.print()

        try:
            choice = input("  Choice: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None

        provider_map = {
            "1": "google",
            "2": "anthropic",
            "3": "openrouter",
            "4": "ollama",
        }

        provider = provider_map.get(choice)
        if provider:
            success = await self.login(provider)
            if success:
                console.print(f"\n  [bold green]✓[/] Successfully authenticated with {provider}!")
                self.show_auth_status(console)
                return provider
            else:
                console.print(f"\n  [bold red]✗[/] Authentication with {provider} failed.")
                return None

        console.print("\n  [dim]Skipped setup. Run 'nexcode --login <provider>' anytime.[/]")
        return None

    # ── API Key auth (interactive) ─────────────────────────────────────────

    def _api_key_login(self, provider: str) -> bool:
        """Prompt user for an API key and store it."""
        env_var = ENV_KEY_MAP.get(provider, "")
        print(f"\n  Enter your {provider.title()} API key")
        print(f"  (or set {env_var} environment variable)\n")

        try:
            key = input("  API Key: ").strip()
        except (EOFError, KeyboardInterrupt):
            return False

        if not key:
            return False

        self._api_keys[provider] = key
        return True

    # ── Google OAuth 2.0 ───────────────────────────────────────────────────

    async def _google_oauth_login(self) -> bool:
        """Run the Google OAuth 2.0 authorization code flow."""
        state = secrets.token_urlsafe(32)

        # Build the authorization URL.
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(GOOGLE_SCOPES),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        auth_url = f"{GOOGLE_AUTH_URI}?{urlencode(params)}"

        # Start a local HTTP server to receive the callback.
        _GoogleCallbackHandler.auth_code = None
        _GoogleCallbackHandler.auth_state = None
        server = HTTPServer(("localhost", GOOGLE_REDIRECT_PORT), _GoogleCallbackHandler)
        server_thread = Thread(target=server.handle_request, daemon=True)
        server_thread.start()

        print("\n  Opening browser for Google login...")
        print(f"  If browser doesn't open, visit:\n  {auth_url}\n")
        webbrowser.open(auth_url)

        # Wait for the callback (max 120 seconds).
        server_thread.join(timeout=120)
        server.server_close()

        code = _GoogleCallbackHandler.auth_code
        returned_state = _GoogleCallbackHandler.auth_state

        if not code:
            print("  ✗ No authorization code received.")
            return False

        if returned_state != state:
            print("  ✗ State mismatch — possible CSRF attack.")
            return False

        # Exchange code for tokens.
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    GOOGLE_TOKEN_URI,
                    data={
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": GOOGLE_REDIRECT_URI,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            print(f"  ✗ Token exchange failed: {exc}")
            return False

        token = OAuthToken(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=time.time() + data.get("expires_in", 3600),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope", ""),
        )

        self._oauth_tokens["google"] = token
        self._save_token("google", token)
        return True

    async def _google_refresh_token(self, token: OAuthToken) -> bool:
        """Refresh an expired Google OAuth token."""
        if not token.refresh_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    GOOGLE_TOKEN_URI,
                    data={
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "refresh_token": token.refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError:
            return False

        token.access_token = data["access_token"]
        token.expires_at = time.time() + data.get("expires_in", 3600)

        self._oauth_tokens["google"] = token
        self._save_token("google", token)
        return True

    # ── GitHub Device Flow ─────────────────────────────────────────────────

    async def _github_device_login(self) -> bool:
        """Run the GitHub OAuth Device Flow."""
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Request device and user codes.
                resp = await client.post(
                    GITHUB_DEVICE_CODE_URL,
                    data={
                        "client_id": GITHUB_CLIENT_ID,
                        "scope": GITHUB_SCOPES,
                    },
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            print(f"  ✗ GitHub device code request failed: {exc}")
            return False

        device_code = data["device_code"]
        user_code = data["user_code"]
        verification_uri = data["verification_uri"]
        interval = data.get("interval", 5)
        expires_in = data.get("expires_in", 900)

        print(f"\n  Go to: [bold]{verification_uri}[/bold]")
        print(f"  Enter code: [bold cyan]{user_code}[/bold cyan]\n")
        print("  Waiting for authorization...")

        webbrowser.open(verification_uri)

        # Step 2: Poll for the access token.
        deadline = time.time() + expires_in

        async with httpx.AsyncClient() as client:
            while time.time() < deadline:
                await _async_sleep(interval)

                try:
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
                except httpx.HTTPError:
                    continue

                if "access_token" in result:
                    token = OAuthToken(
                        access_token=result["access_token"],
                        refresh_token=result.get("refresh_token"),
                        token_type=result.get("token_type", "bearer"),
                        scope=result.get("scope", ""),
                    )
                    self._oauth_tokens["github"] = token
                    self._save_token("github", token)
                    return True

                error = result.get("error")
                if error == "authorization_pending":
                    continue
                elif error == "slow_down":
                    interval += 5
                elif error in ("expired_token", "access_denied"):
                    print(f"  ✗ GitHub authorization failed: {error}")
                    return False

        print("  ✗ GitHub authorization timed out.")
        return False

    # ── Ollama auto-detection ──────────────────────────────────────────────

    async def _ollama_detect(self) -> bool:
        """Check if Ollama is running and list available models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Ping Ollama.
                resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                resp.raise_for_status()
                data = resp.json()

            models = [m["name"] for m in data.get("models", [])]
            self._ollama_models = models

            if models:
                print(f"  ✓ Ollama detected — {len(models)} model(s) available:")
                for m in models[:10]:
                    print(f"    • {m}")
                if len(models) > 10:
                    print(f"    ... and {len(models) - 10} more")
                return True
            else:
                print("  ⚠ Ollama is running but no models are installed.")
                print("  Run: ollama pull llama3.1")
                return False

        except (httpx.HTTPError, httpx.ConnectError, OSError):
            print("  ✗ Ollama is not running at localhost:11434")
            print("  Install: https://ollama.ai")
            return False

    # ── Token persistence ──────────────────────────────────────────────────

    def _save_token(self, provider: str, token: OAuthToken) -> None:
        """Persist an OAuth token to disk."""
        path = NEXCODE_DIR / f"{provider}_token.json"
        path.write_text(
            json.dumps(token.to_dict(), indent=2),
            encoding="utf-8",
        )

    def _load_tokens(self) -> None:
        """Load all persisted OAuth tokens from disk."""
        for provider in OAUTH_PROVIDERS:
            path = NEXCODE_DIR / f"{provider}_token.json"
            if path.is_file():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    self._oauth_tokens[provider] = OAuthToken.from_dict(data)
                except (json.JSONDecodeError, KeyError):
                    pass  # Corrupt token file — ignore.

    def set_api_key(self, provider: str, key: str) -> None:
        """Programmatically set an API key for a provider."""
        self._api_keys[provider.lower()] = key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _async_sleep(seconds: float) -> None:
    """Async-compatible sleep helper."""
    import asyncio
    await asyncio.sleep(seconds)
