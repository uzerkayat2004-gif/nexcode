"""
NexCode Safety Sandbox
~~~~~~~~~~~~~~~~~~~~~~~

Validates shell commands against safety rules before execution.
Blocks dangerous patterns, warns on risky ones, and provides
cross-platform shell adaptation.
"""

import platform
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# SandboxResult
# ---------------------------------------------------------------------------


@dataclass
class SandboxResult:
    """Result of a sandbox safety check."""

    allowed: bool
    risk_level: str  # "safe", "warn", "blocked"
    reason: str | None = None
    suggested_safe_alternative: str | None = None


# ---------------------------------------------------------------------------
# Blocked / warned command patterns
# ---------------------------------------------------------------------------

# Commands that are ALWAYS blocked — catastrophic, irreversible.
ALWAYS_BLOCKED: list[tuple[str, str]] = [
    (r"rm\s+-rf\s+/\s*$", "Deleting root filesystem"),
    (r"rm\s+-rf\s+/\*", "Deleting root filesystem"),
    (r"rm\s+-rf\s+~/?$", "Deleting home directory"),
    (r"rm\s+-rf\s+\$HOME", "Deleting home directory"),
    (r"mkfs\.", "Formatting disk"),
    (r"dd\s+.*of=/dev/", "Writing to raw disk device"),
    (r"chmod\s+-R\s+777\s+/\s*$", "Unrestricting root permissions"),
    (r":\(\)\{\s*:\|:&\s*\};:", "Fork bomb"),
    (r"curl\s+.*\|\s*s(h|udo)", "Piping remote content to shell"),
    (r"wget\s+.*\|\s*s(h|udo)", "Piping remote content to shell"),
    (r">\s*/dev/sda", "Overwriting disk device"),
    (r"mv\s+/\s+/dev/null", "Moving root to null device"),
]

# Commands that trigger a warning — risky but sometimes intended.
WARN_BEFORE: list[tuple[str, str]] = [
    (r"rm\s+-rf\b", "Recursive force delete"),
    (r"rm\s+-r\b", "Recursive delete"),
    (r"DROP\s+TABLE", "SQL table drop"),
    (r"DROP\s+DATABASE", "SQL database drop"),
    (r"TRUNCATE\s+TABLE", "SQL table truncation"),
    (r"git\s+push\s+--force", "Git force push"),
    (r"git\s+push\s+-f\b", "Git force push"),
    (r"git\s+reset\s+--hard", "Git hard reset"),
    (r"git\s+clean\s+-fd", "Git clean force"),
    (r"npm\s+publish", "Publishing to npm"),
    (r"pip\s+install\b", "Installing Python packages"),
    (r"npm\s+install\s+-g", "Global npm install"),
    (r"sudo\b", "Elevated privileges"),
    (r"chmod\s+-R\b", "Recursive permission change"),
    (r"chown\s+-R\b", "Recursive ownership change"),
    (r"docker\s+system\s+prune", "Docker system cleanup"),
]


# ---------------------------------------------------------------------------
# PlatformAdapter — cross-platform shell compatibility
# ---------------------------------------------------------------------------


class PlatformAdapter:
    """Cross-platform shell and path adaptation."""

    @staticmethod
    def get_shell() -> list[str]:
        """Return the shell command prefix for the current OS."""
        system = platform.system()
        if system == "Windows":
            # Prefer PowerShell, fall back to cmd.
            if shutil.which("pwsh"):
                return ["pwsh", "-NoProfile", "-Command"]
            elif shutil.which("powershell"):
                return ["powershell", "-NoProfile", "-Command"]
            else:
                return ["cmd", "/c"]
        else:
            # Unix — prefer bash, fall back to sh.
            if shutil.which("bash"):
                return ["/bin/bash", "-c"]
            else:
                return ["/bin/sh", "-c"]

    @staticmethod
    def normalize_path(path: str) -> str:
        """Normalize path separators for the current OS."""
        return str(Path(path))

    @staticmethod
    def get_env_separator() -> str:
        """Return PATH separator for the current OS."""
        return ";" if platform.system() == "Windows" else ":"

    @staticmethod
    def is_windows() -> bool:
        return platform.system() == "Windows"

    @staticmethod
    def is_wsl() -> bool:
        """Detect if running inside WSL on Windows."""
        if platform.system() != "Linux":
            return False
        try:
            with open("/proc/version") as f:
                return "microsoft" in f.read().lower()
        except OSError:
            return False

    @staticmethod
    def get_system_info() -> dict[str, str]:
        """Return basic system information."""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "is_wsl": str(PlatformAdapter.is_wsl()),
        }


# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------


class Sandbox:
    """
    Safety layer that validates commands before execution.

    Checks commands against blocked and warned pattern lists,
    supports configurable whitelist/blacklist overrides.
    """

    def __init__(self) -> None:
        self._whitelist: list[str] = []
        self._blacklist: list[str] = []

    def check(self, command: str) -> SandboxResult:
        """
        Validate a command against safety rules.

        Returns a ``SandboxResult`` indicating whether the command
        is safe, needs a warning, or is blocked.
        """
        normalized = command.strip()

        # Check custom blacklist first.
        for pattern in self._blacklist:
            if re.search(pattern, normalized, re.IGNORECASE):
                return SandboxResult(
                    allowed=False,
                    risk_level="blocked",
                    reason=f"Matches custom blacklist pattern: {pattern}",
                )

        # Check custom whitelist — overrides built-in rules.
        for pattern in self._whitelist:
            if re.search(pattern, normalized, re.IGNORECASE):
                return SandboxResult(
                    allowed=True,
                    risk_level="safe",
                    reason="Whitelisted",
                )

        # Check always-blocked patterns.
        for pattern, reason in ALWAYS_BLOCKED:
            if re.search(pattern, normalized, re.IGNORECASE):
                return SandboxResult(
                    allowed=False,
                    risk_level="blocked",
                    reason=f"Blocked: {reason}",
                    suggested_safe_alternative=_suggest_alternative(normalized),
                )

        # Check warned patterns.
        for pattern, reason in WARN_BEFORE:
            if re.search(pattern, normalized, re.IGNORECASE):
                return SandboxResult(
                    allowed=True,
                    risk_level="warn",
                    reason=f"Warning: {reason}",
                )

        # No matches — safe.
        return SandboxResult(
            allowed=True,
            risk_level="safe",
        )

    def whitelist(self, pattern: str) -> None:
        """Add a regex pattern to the whitelist (overrides built-in rules)."""
        self._whitelist.append(pattern)

    def blacklist(self, pattern: str) -> None:
        """Add a regex pattern to the blacklist (blocks matching commands)."""
        self._blacklist.append(pattern)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _suggest_alternative(command: str) -> str | None:
    """Suggest a safer alternative for a blocked command."""
    if re.search(r"rm\s+-rf", command):
        return "Use 'rm -ri' for interactive deletion, or delete specific files."
    if re.search(r"curl.*\|\s*sh", command):
        return "Download the script first with 'curl -O', review it, then run."
    return None
