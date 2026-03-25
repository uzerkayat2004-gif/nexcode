"""
NexCode Guardian — Master Safety Controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Single entry point that orchestrates safety rules,
permission checks, audit logging, and checkpointing.
Every tool execution must go through the Guardian.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from nexcode.safety.audit import AuditEntry, AuditLog
from nexcode.safety.permissions import (
    RISK_MATRIX,
    PermissionManager,
    PermissionRequest,
)
from nexcode.safety.rules import RuleViolation, SafetyRules

# ---------------------------------------------------------------------------
# GuardianDecision
# ---------------------------------------------------------------------------

@dataclass
class GuardianDecision:
    """Final decision from the Guardian."""

    approved: bool
    reason: str
    auto_approved: bool = False
    violations: list[RuleViolation] = field(default_factory=list)
    checkpoint_required: bool = False


# ---------------------------------------------------------------------------
# Guardian
# ---------------------------------------------------------------------------

class Guardian:
    """
    Master safety controller for NexCode.

    Decision flow:
    1. Safety rules check (block / warn)
    2. Permission check (risk-based prompt)
    3. Audit log entry
    4. Checkpoint if needed
    """

    def __init__(
        self,
        mode: str = "ask",
        project_root: str | None = None,
        session_id: str = "",
        console: Console | None = None,
    ) -> None:
        self.console = console or Console()
        self.rules = SafetyRules(project_root)
        self.permissions = PermissionManager(mode=mode, console=self.console)
        self.audit = AuditLog(session_id=session_id, console=self.console)
        self._emergency_stop = False

    # ── Master approval ────────────────────────────────────────────────────

    async def approve(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        context: str | None = None,
    ) -> GuardianDecision:
        """
        Master check — called before EVERY tool execution.

        Returns whether the action is approved, with full context.
        """
        import time
        start = time.perf_counter()

        if self._emergency_stop:
            self._log_entry(tool_name, parameters, "blocked", "blocked", "safe", 0)
            return GuardianDecision(
                approved=False,
                reason="Emergency stop is active",
            )

        # Step 1: Safety rules check.
        violations = self.rules.evaluate(tool_name, parameters)

        if self.rules.has_blocks(violations):
            # Hard block — never execute.
            block = next(v for v in violations if v.severity == "block")
            self._show_block(tool_name, block)
            self._log_entry(tool_name, parameters, "blocked", "blocked", "critical", 0)
            return GuardianDecision(
                approved=False,
                reason=f"Blocked by rule {block.rule_id}: {block.message}",
                violations=violations,
            )

        if self.rules.has_warnings(violations):
            # Show warnings — user must acknowledge.
            for warn in (v for v in violations if v.severity == "warn"):
                self._show_warning(warn)

        # Step 2: Permission check.
        risk = RISK_MATRIX.get(tool_name, "medium")
        affected = self._extract_paths(parameters)
        command = parameters.get("command")

        req = PermissionRequest(
            tool_name=tool_name,
            action=self._action_description(tool_name, parameters),
            details=parameters,
            risk_level=risk,
            reversible=tool_name not in ("delete_file", "git_reset", "git_push"),
            affected_paths=affected,
            command=command,
        )

        decision = await self.permissions.request(req)
        auto = decision.scope != "once" or risk == "safe"

        # Step 3: Audit log.
        elapsed = int((time.perf_counter() - start) * 1000)
        perm_label = "auto" if auto else ("user_approved" if decision.granted else "user_denied")
        result_label = "success" if decision.granted else "skipped"
        self._log_entry(tool_name, parameters, perm_label, result_label, risk, elapsed, affected)

        # Step 4: Determine checkpoint need.
        checkpoint = tool_name in (
            "write_file", "edit_file", "create_file",
            "delete_file", "move_file", "search_and_replace",
        )

        return GuardianDecision(
            approved=decision.granted,
            reason=decision.reason or ("Approved" if decision.granted else "Denied"),
            auto_approved=auto,
            violations=violations,
            checkpoint_required=checkpoint and decision.granted,
        )

    # ── Dashboard ──────────────────────────────────────────────────────────

    def show_dashboard(self) -> None:
        """Show safety dashboard."""
        stats = self.permissions.stats
        body = Text()
        body.append(f"  Permission Mode:  {self.permissions.mode}\n", style="bold white")
        body.append(f"  Session actions:   {stats['approved'] + stats['denied'] + stats['blocked']}\n", style="white")
        body.append(f"  Blocked:           {stats['blocked']} critical actions\n", style="red" if stats["blocked"] else "dim")
        body.append(f"  Audit entries:     {self.audit.total_entries_today} today\n", style="dim")

        # Session grants.
        grants = self.permissions._session_grants
        if grants:
            body.append("\n  Pre-approved this session:\n", style="bold")
            for tool, pattern in grants.items():
                body.append(f"    ✅ {tool} ({pattern})\n", style="green")

        # Always denied.
        denies = self.permissions._always_denies
        if denies:
            body.append("\n  Always blocked:\n", style="bold")
            for tool in denies:
                body.append(f"    🛑 {tool}\n", style="red")

        # Ignore patterns.
        patterns = self.rules.ignore_patterns
        if patterns:
            body.append(f"\n  .nexcode-ignore ({len(patterns)} patterns)\n", style="dim")

        self.console.print(Panel(
            body,
            title=" 🛡️  NexCode Safety Dashboard ",
            title_align="left",
            border_style="bright_blue",
            padding=(0, 1),
        ))

    def show_permissions(self) -> None:
        """Show current permission rules."""
        self.permissions.show_rules()

    # ── Emergency controls ─────────────────────────────────────────────────

    def emergency_stop(self) -> None:
        """Block all actions immediately."""
        self._emergency_stop = True
        self.permissions.emergency_stop()
        self.console.print("  [bold red]🛑 Emergency stop activated — all actions blocked[/]")

    def resume(self) -> None:
        """Resume from emergency stop."""
        self._emergency_stop = False
        self.permissions.resume()
        self.console.print("  [green]✅ Resumed — actions allowed[/]")

    # ── Internal display ───────────────────────────────────────────────────

    def _show_block(self, tool_name: str, violation: RuleViolation) -> None:
        body = Text()
        body.append(f"\n  🚫 BLOCKED: {tool_name}\n\n", style="bold red")
        body.append(f"  Rule: {violation.rule_id}\n", style="white")
        body.append(f"  Reason: {violation.message}\n", style="white")
        if violation.suggestion:
            body.append(f"  Suggestion: {violation.suggestion}\n", style="dim")

        self.console.print(Panel(
            body, title=" 🛑 Action Blocked ", title_align="left",
            border_style="bright_red", padding=(0, 1),
        ))

    def _show_warning(self, violation: RuleViolation) -> None:
        self.console.print(
            f"  [yellow]⚠️  Warning [{violation.rule_id}]: {violation.message}[/]"
        )

    def _show_ignore_block(self, path: str) -> None:
        body = Text()
        body.append(f"\n  Path: {path}\n", style="white")
        body.append("  Reason: Listed in .nexcode-ignore\n\n", style="dim")
        body.append("  This file is protected. To allow access,\n", style="dim")
        body.append("  remove it from .nexcode-ignore\n", style="dim")

        self.console.print(Panel(
            body, title=" 🚫 Access Denied ", title_align="left",
            border_style="red", padding=(0, 1),
        ))

    # ── Helpers ────────────────────────────────────────────────────────────

    def _extract_paths(self, params: dict[str, Any]) -> list[str]:
        paths: list[str] = []
        for key in ("path", "source", "destination", "target", "file_path"):
            val = params.get(key)
            if isinstance(val, str) and val:
                paths.append(val)
        arr = params.get("paths", [])
        if isinstance(arr, list):
            paths.extend(str(p) for p in arr if p)
        return paths[:5]

    def _action_description(self, tool_name: str, params: dict[str, Any]) -> str:
        """Generate human-readable action description."""
        descriptions: dict[str, str] = {
            "read_file": "Read file",
            "write_file": "Write file",
            "create_file": "Create new file",
            "edit_file": "Edit file",
            "delete_file": "Delete file",
            "move_file": "Move/rename file",
            "copy_file": "Copy file",
            "run_command": "Execute shell command",
            "run_script": "Run script",
            "run_tests": "Run test suite",
            "install_dependencies": "Install packages",
            "git_push": "Push to remote",
            "git_push_force": "Force push to remote",
            "git_reset": "Reset git state",
            "git_commit": "Create commit",
        }
        return descriptions.get(tool_name, f"Execute {tool_name}")

    def _log_entry(
        self,
        tool_name: str,
        params: dict[str, Any],
        decision: str,
        result: str,
        risk: str,
        duration_ms: int,
        files: list[str] | None = None,
    ) -> None:
        self.audit.log(AuditEntry(
            id=uuid.uuid4().hex[:10],
            tool_name=tool_name,
            parameters=params,
            permission_decision=decision,
            result=result,
            risk_level=risk,
            duration_ms=duration_ms,
            files_affected=files or self._extract_paths(params),
        ))
