"""
NexCode Configuration System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Loads and manages configuration from .nexcode.toml files.
Supports hierarchical resolution: defaults → user config → project config → env vars.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

# tomli is built-in as tomllib in Python 3.11+, but we keep the
# dependency for explicit version control.
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CONFIG_LOCK = asyncio.Lock()


DEFAULT_MODEL: str = "claude-opus-4-6"
DEFAULT_PROVIDER: str = "anthropic"
DEFAULT_MAX_TOKENS: int = 4000
DEFAULT_THEME: str = "dark"
DEFAULT_PERMISSION_MODE: str = "ask"
DEFAULT_WORKSPACE_FILE: str = "NEXCODE.md"

VALID_PERMISSION_MODES: set[str] = {"ask", "auto", "strict"}
VALID_THEMES: set[str] = {"dark", "light"}

# Well-known env var names for API keys per provider.
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


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

@dataclass
class NexCodeConfig:
    """Immutable configuration object for NexCode."""

    default_model: str = DEFAULT_MODEL
    default_provider: str = DEFAULT_PROVIDER
    api_keys: dict[str, str] = field(default_factory=dict)
    permission_mode: Literal["ask", "auto", "strict"] = DEFAULT_PERMISSION_MODE  # type: ignore[assignment]
    max_tokens: int = DEFAULT_MAX_TOKENS
    theme: Literal["dark", "light"] = DEFAULT_THEME  # type: ignore[assignment]
    auto_save_session: bool = True
    workspace_file: str = DEFAULT_WORKSPACE_FILE

    # Internal: paths where config was loaded from (for debugging).
    _loaded_from: list[str] = field(default_factory=list, repr=False)

    def get_api_key(self, provider: str | None = None) -> str | None:
        """Return the API key for *provider*, checking env vars first."""
        provider = provider or self.default_provider
        env_var = ENV_KEY_MAP.get(provider)
        if env_var:
            env_value = os.environ.get(env_var)
            if env_value:
                return env_value
        return self.api_keys.get(provider)

    def has_api_key(self, provider: str | None = None) -> bool:
        """Check whether an API key is available for the given provider."""
        return self.get_api_key(provider) is not None


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _find_config_paths() -> list[Path]:
    """
    Return a list of config file paths in resolution order (lowest → highest priority):
      1. User-level: ~/.nexcode.toml
      2. Project-level: ./.nexcode.toml
    """
    paths: list[Path] = []

    # User-level config.
    user_config = Path.home() / ".nexcode.toml"
    if user_config.is_file():
        paths.append(user_config)

    # Project-level config (cwd).
    project_config = Path.cwd() / ".nexcode.toml"
    if project_config.is_file() and project_config.resolve() != user_config.resolve():
        paths.append(project_config)

    return paths


def _parse_toml(path: Path) -> dict[str, Any]:
    """Read and parse a TOML file, returning an empty dict on failure."""
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception as exc:
        # Non-fatal: bad config should not crash the app on startup.
        import warnings
        warnings.warn(f"Failed to parse config '{path}': {exc}", stacklevel=2)
        return {}


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge *override* into *base* (override wins)."""
    merged = {**base}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _validate_config(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and coerce raw config values, raising on fatal errors."""
    if "permission_mode" in data:
        mode = data["permission_mode"]
        if mode not in VALID_PERMISSION_MODES:
            raise ValueError(
                f"Invalid permission_mode '{mode}'. "
                f"Must be one of: {', '.join(sorted(VALID_PERMISSION_MODES))}"
            )

    if "theme" in data:
        theme = data["theme"]
        if theme not in VALID_THEMES:
            raise ValueError(
                f"Invalid theme '{theme}'. "
                f"Must be one of: {', '.join(sorted(VALID_THEMES))}"
            )

    if "max_tokens" in data:
        try:
            data["max_tokens"] = int(data["max_tokens"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"max_tokens must be an integer: {exc}") from exc

    return data


def load_config() -> NexCodeConfig:
    """
    Load the NexCode configuration by merging defaults with user and project
    config files.  Environment variables for API keys take final precedence
    at access time (via ``NexCodeConfig.get_api_key``).

    Returns:
        A fully-resolved ``NexCodeConfig`` instance.
    """
    merged: dict[str, Any] = {}
    loaded_from: list[str] = []

    for path in _find_config_paths():
        data = _parse_toml(path)
        if data:
            merged = _merge_dict(merged, data)
            loaded_from.append(str(path))

    merged = _validate_config(merged)

    # Build config from merged values, falling back to dataclass defaults.
    config = NexCodeConfig(
        default_model=merged.get("default_model", DEFAULT_MODEL),
        default_provider=merged.get("default_provider", DEFAULT_PROVIDER),
        api_keys=merged.get("api_keys", {}),
        permission_mode=merged.get("permission_mode", DEFAULT_PERMISSION_MODE),
        max_tokens=merged.get("max_tokens", DEFAULT_MAX_TOKENS),
        theme=merged.get("theme", DEFAULT_THEME),
        auto_save_session=merged.get("auto_save_session", True),
        workspace_file=merged.get("workspace_file", DEFAULT_WORKSPACE_FILE),
        _loaded_from=loaded_from,
    )

    return config


def save_config(config: NexCodeConfig, path: Path | None = None) -> Path:
    """
    Serialize the current config to a TOML file.

    Args:
        config: The config object to save.
        path: Destination path.  Defaults to ``~/.nexcode.toml``.

    Returns:
        The path the config was written to.
    """
    if path is None:
        path = Path.home() / ".nexcode.toml"

    data: dict[str, Any] = {
        "default_model": config.default_model,
        "default_provider": config.default_provider,
        "permission_mode": config.permission_mode,
        "max_tokens": config.max_tokens,
        "theme": config.theme,
        "auto_save_session": config.auto_save_session,
        "workspace_file": config.workspace_file,
    }

    if config.api_keys:
        data["api_keys"] = config.api_keys

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        tomli_w.dump(data, fh)

    return path


async def save_config_async(config: NexCodeConfig, path: Path | None = None) -> Path:
    """
    Serialize the current config to a TOML file asynchronously.
    Uses asyncio.to_thread to offload file I/O to a worker thread and a
    module-level lock to prevent race conditions during concurrent writes.

    Args:
        config: The config object to save.
        path: Destination path. Defaults to ``~/.nexcode.toml``.

    Returns:
        The path the config was written to.
    """
    async with _CONFIG_LOCK:
        return await asyncio.to_thread(save_config, config, path)
