"""
NexCode Permission Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Decides whether any action is allowed based on risk level,
permission mode, and user decisions.  Shows tiered Rich
prompts from silent auto-approve to typed confirmation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# ---------------------------------------------------------------------------
# Risk matrix — auto-assigned risk for every tool
# ---------------------------------------------------------------------------

RISK_MATRIX: dict[str, str] = {
    # SAFE — never ask
    "read_file":            "safe",
    "list_directory":       "safe",
    "find_files":           "safe",
    "search_text":          "safe",
    "read_many_files":      "safe",
    "git_status":           "safe",
    "git_log":              "safe",
    "git_diff":             "safe",
    "git_blame":            "safe",
    "file_info":            "safe",
    "which":                "safe",

    # LOW — ask once per session
    "create_file":          "low",
    "write_file":           "low",
    "edit_file":            "low",
    "copy_file":            "low",
    "move_file":            "low",
    "git_stage":            "low",
    "git_unstage":          "low",
    "git_commit":           "low",
    "set_environment":      "low",
    "git_tag":              "low",

    # MEDIUM — ask every time
    "run_command":          "medium",
    "run_script":           "medium",
    "run_tests":            "medium",
    "install_dependencies": "medium",
    "search_and_replace":   "medium",
    "git_push":             "medium",
    "git_pull":             "medium",
    "git_branch":           "medium",
    "git_stash":            "medium",
    "start_background":     "medium",

    # HIGH — always ask with detailed warning
    "delete_file":          "high",
    "git_reset":            "high",
    "git_restore":          "high",
    "stop_background":      "high",
}

# Critical overrides (detected from parameters at runtime).
_CRITICAL_PATTERNS: dict[str, str] = {
    "git_push__force":      "critical",
    "git_reset__hard":      "critical",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PermissionRequest:
    """A request for permission to execute an action."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    tool_name: str = ""
    action: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"
    reversible: bool = True
    affected_paths: list[str] = field(default_factory=list)
    command: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PermissionDecision:
    """The result of a permission check."""

    granted: bool
    scope: str = "once"       # "once", "session", "always", "denied"
    reason: str | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# PermissionManager
# ---------------------------------------------------------------------------

class PermissionManager:
    """
    Core permission system.  Checks every tool call against risk
    matrix, mode, and prior grants.  Shows tiered Rich prompts.

    Modes: ask (default), auto, strict, yolo
    """

    def __init__(self, mode: str = "ask", console: Console | None = None) -> None:
        self.mode = mode
        self.console = console or Console()
        self._session_grants: dict[str, str] = {}   # tool -> pattern
        self._always_grants: dict[str, str] = {}
        self._always_denies: set[str] = set()
        self._emergency_stop = False
        self._stats = {"approved": 0, "denied": 0, "blocked": 0}

    # ── Main permission check ──────────────────────────────────────────────

    async def request(self, req: PermissionRequest) -> PermissionDecision:
        """Main entry point — check whether an action is allowed."""
        if self._emergency_stop:
            return PermissionDecision(granted=False, scope="denied", reason="Emergency stop active")

        # Determine effective risk level.
        risk = self._effective_risk(req)
        req.risk_level = risk

        # Check always-deny list.
        if req.tool_name in self._always_denies:
            self._stats["denied"] += 1
            return PermissionDecision(granted=False, scope="denied", reason="Permanently denied")

        # Mode-based auto-approve logic.
        if self.mode == "yolo":
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="session", reason="YOLO mode")

        if self.mode == "auto" and risk != "critical":
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="session", reason="Auto mode")

        if risk == "safe" and self.mode != "strict":
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="once", reason="Safe action")

        # Check pre-approved grants.
        if self.is_pre_approved(req):
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="session", reason="Pre-approved")

        # Show appropriate prompt.
        if risk == "low":
            return self._prompt_low(req)
        elif risk == "medium":
            return self._prompt_medium(req)
        elif risk == "high":
            return self._prompt_high(req)
        elif risk == "critical":
            return self._prompt_critical(req)
        else:
            return self._prompt_medium(req)

    # ── Grant management ───────────────────────────────────────────────────

    def grant_session(self, tool_name: str, pattern: str | None = None) -> None:
        self._session_grants[tool_name] = pattern or "*"

    def grant_always(self, tool_name: str, pattern: str | None = None) -> None:
        self._always_grants[tool_name] = pattern or "*"

    def deny_always(self, tool_name: str, pattern: str | None = None) -> None:
        self._always_denies.add(tool_name)

    def is_pre_approved(self, req: PermissionRequest) -> bool:
        if req.tool_name in self._session_grants:
            return True
        if req.tool_name in self._always_grants:
            return True
        return False

    def reset_session(self) -> None:
        self._session_grants.clear()
        self._emergency_stop = False

    # ── Display ────────────────────────────────────────────────────────────

    def show_rules(self) -> None:
        """Show current permission rules."""
        from rich.table import Table

        table = Table(title="🛡️ Permission Rules", border_style="bright_black")
        table.add_column("Scope", min_width=10)
        table.add_column("Tool", min_width=18)
        table.add_column("Status")

        for tool, pattern in self._session_grants.items():
            table.add_row("Session", tool, f"[green]✅ Allowed[/] ({pattern})")
        for tool, pattern in self._always_grants.items():
            table.add_row("Always", tool, f"[green]✅ Allowed[/] ({pattern})")
        for tool in self._always_denies:
            table.add_row("Always", tool, "[red]🛑 Denied[/]")

        self.console.print()
        self.console.print(table)
        self.console.print(f"\n  Mode: [bold]{self.mode}[/] │ "
                           f"Approved: {self._stats['approved']} │ "
                           f"Denied: {self._stats['denied']} │ "
                           f"Blocked: {self._stats['blocked']}")

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    # ── Emergency stop ─────────────────────────────────────────────────────

    def emergency_stop(self) -> None:
        self._emergency_stop = True

    def resume(self) -> None:
        self._emergency_stop = False

    # ── Prompt tiers ───────────────────────────────────────────────────────

    def _prompt_low(self, req: PermissionRequest) -> PermissionDecision:
        """Low risk: simple [y/n/s] prompt."""
        body = Text()
        body.append(f"  {req.tool_name}\n", style="bold cyan")
        if req.affected_paths:
            body.append(f"  Path: {req.affected_paths[0]}\n", style="white")
        body.append(f"  Action: {req.action}\n", style="dim")

        self.console.print(Panel(
            body, title=" 🔧 Tool Request ", title_align="left",
            border_style="cyan", padding=(0, 1),
        ))
        self.console.print("  [y] Yes  [n] No  [s] Yes for session")

        choice = self._get_input()
        if choice in ("y", "yes", ""):
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="once")
        elif choice == "s":
            self.grant_session(req.tool_name)
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="session")
        else:
            self._stats["denied"] += 1
            return PermissionDecision(granted=False, scope="denied", reason="User denied")

    def _prompt_medium(self, req: PermissionRequest) -> PermissionDecision:
        """Medium risk: detailed prompt with [y/n/s/a]."""
        body = Text()
        body.append(f"  {req.tool_name}\n\n", style="bold cyan")
        if req.command:
            body.append(f"  $ {req.command}\n\n", style="white")
        if req.affected_paths:
            body.append(f"  Paths: {', '.join(req.affected_paths[:3])}\n", style="dim")
        rev = "Yes" if req.reversible else "No"
        body.append(f"  Risk: {req.risk_level.capitalize()}  │  Reversible: {rev}\n", style="dim")

        self.console.print(Panel(
            body, title=" ⚠️  Permission Required ", title_align="left",
            border_style="yellow", padding=(0, 1),
        ))
        self.console.print("  [y] Yes  [n] No  [s] Yes for session  [a] Always allow")

        choice = self._get_input()
        if choice in ("y", "yes", ""):
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="once")
        elif choice == "s":
            self.grant_session(req.tool_name)
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="session")
        elif choice == "a":
            self.grant_always(req.tool_name)
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="always")
        else:
            self._stats["denied"] += 1
            return PermissionDecision(granted=False, scope="denied", reason="User denied")

    def _prompt_high(self, req: PermissionRequest) -> PermissionDecision:
        """High risk: detailed warning, must type 'yes'."""
        body = Text()
        body.append(f"\n  {req.action.upper()}\n", style="bold red")
        if req.affected_paths:
            body.append(f"  Path: {req.affected_paths[0]}\n\n", style="white")
        body.append("  ⚠️  This action is HIGH RISK\n", style="yellow")
        if req.reversible:
            body.append("  ✅  Recoverable with /rewind\n", style="green")
        else:
            body.append("  ❌  This CANNOT be undone\n", style="red")

        self.console.print(Panel(
            body, title=" 🚨 High Risk Action ", title_align="left",
            border_style="red", padding=(0, 1),
        ))
        self.console.print('  Type "yes" to confirm or press Enter to cancel:')

        choice = self._get_input()
        if choice == "yes":
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="once")
        else:
            self._stats["denied"] += 1
            return PermissionDecision(granted=False, scope="denied", reason="User did not confirm")

    def _prompt_critical(self, req: PermissionRequest) -> PermissionDecision:
        """Critical risk: must type specific confirmation value."""
        body = Text()
        body.append(f"\n  {req.tool_name}\n", style="bold white")
        if req.command:
            body.append(f"  {req.command}\n\n", style="white")
        body.append("  ❌ THIS ACTION IS CRITICAL AND MAY BE IRREVERSIBLE\n", style="bold red")
        body.append("  ❌ REVIEW CAREFULLY BEFORE PROCEEDING\n", style="red")

        self.console.print(Panel(
            body, title=" 🛑 CRITICAL ACTION — READ CAREFULLY ", title_align="left",
            border_style="bright_red", padding=(0, 1),
        ))

        # Require typing a confirmation word.
        confirm_word = "CONFIRM"
        if req.affected_paths:
            confirm_word = req.affected_paths[0].split("/")[-1]
        self.console.print(f'  Type "{confirm_word}" to proceed:')

        choice = self._get_input()
        if choice == confirm_word or choice == confirm_word.lower():
            self._stats["approved"] += 1
            return PermissionDecision(granted=True, scope="once")
        else:
            self._stats["denied"] += 1
            return PermissionDecision(granted=False, scope="denied", reason="Confirmation mismatch")

    # ── Internal ───────────────────────────────────────────────────────────

    def _effective_risk(self, req: PermissionRequest) -> str:
        """Determine effective risk level, with critical overrides."""
        base_risk = RISK_MATRIX.get(req.tool_name, "medium")

        # Upgrade to critical for dangerous parameter combos.
        if req.tool_name == "git_push" and req.details.get("force"):
            return "critical"
        if req.tool_name == "git_reset" and req.details.get("mode") == "hard":
            return "critical"
        if req.tool_name == "run_command":
            cmd = req.details.get("command", "")
            if any(kw in cmd for kw in ["rm -rf", "sudo", "format", "mkfs"]):
                return "critical"

        return base_risk

    def _get_input(self) -> str:
        try:
            return input("  › ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "n"
