"""
NexCode Safety Rules Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Evaluates every action against comprehensive block/warn
rulesets covering shell commands, file paths, and
.nexcode-ignore patterns.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# RuleViolation
# ---------------------------------------------------------------------------

@dataclass
class RuleViolation:
    """A single rule violation detected."""

    rule_id: str
    severity: str          # "block", "warn", "info"
    message: str
    suggestion: str | None = None


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

@dataclass
class _Rule:
    id: str
    pattern: str | None = None     # regex for commands
    path_pattern: str | None = None  # path prefix
    message: str = ""
    suggestion: str | None = None


# — BLOCK rules — hard stop, never execute —

_BLOCK_RULES: list[_Rule] = [
    _Rule("SH001", r"rm\s+-rf\s+/\s*$",      None, "Attempt to delete root filesystem", "Use a specific path instead"),
    _Rule("SH002", r"rm\s+-rf\s+~",           None, "Attempt to delete home directory", "Use a specific path instead"),
    _Rule("SH003", r"\bmkfs\b",               None, "Attempt to format disk", "This is extremely dangerous"),
    _Rule("SH004", r"dd\s+.*of=/dev/sd",      None, "Attempt to write to disk device", "This can destroy your system"),
    _Rule("SH005", r":\(\)\{\s*:\|:&\s*\};:", None, "Fork bomb detected", "This will crash your system"),
    _Rule("SH006", r"curl\s+.*\|\s*(ba)?sh",  None, "Curl pipe to shell — code injection risk", "Download first, review, then run"),
    _Rule("SH007", r"wget\s+.*\|\s*(ba)?sh",  None, "Wget pipe to shell — code injection risk", "Download first, review, then run"),
    _Rule("SH008", r"chmod\s+-R\s+777\s+/",   None, "Recursive chmod 777 on root", "Use specific permissions instead"),
    _Rule("SH009", r"\bsudo\s+rm\s+-rf",      None, "Sudo recursive delete", "Use a specific path without sudo"),
    # Path-based blocks.
    _Rule("PT001", None, "/etc/passwd",   "Attempt to modify system auth file"),
    _Rule("PT002", None, "/etc/shadow",   "Attempt to modify system password file"),
    _Rule("PT003", None, "/boot/",        "Attempt to modify boot directory"),
    _Rule("PT004", None, "~/.ssh/",       "Attempt to modify SSH keys", "SSH keys are sensitive — modify manually"),
    _Rule("PT005", None, "~/.nexcode/",   "Attempt to modify NexCode internals", "Use NexCode commands instead"),
]

# — WARN rules — show warning, require confirmation —

_WARN_RULES: list[_Rule] = [
    _Rule("WN001", r"rm\s+-rf",              None, "Recursive delete — cannot be undone"),
    _Rule("WN002", r"git\s+push\s+--force",  None, "Force push will rewrite remote history"),
    _Rule("WN003", r"DROP\s+TABLE",          None, "SQL table drop is irreversible"),
    _Rule("WN004", r"DROP\s+DATABASE",       None, "SQL database drop is irreversible"),
    _Rule("WN005", r"npm\s+publish",         None, "This will publish to public npm registry"),
    _Rule("WN006", r"pip\s+install",         None, "Installing packages modifies your environment"),
    _Rule("WN007", r"git\s+reset\s+--hard",  None, "Hard reset will permanently discard changes"),
    _Rule("WN008", r"\btruncate\b",          None, "Truncate will erase file contents"),
    _Rule("WN009", r"\bshred\b",             None, "Shred permanently destroys files"),
    _Rule("WN010", r"git\s+clean\s+-fd",     None, "Removes all untracked files permanently"),
]


# ---------------------------------------------------------------------------
# SafetyRules
# ---------------------------------------------------------------------------

class SafetyRules:
    """
    Evaluates actions against block/warn rulesets and .nexcode-ignore.
    """

    def __init__(self, project_root: str | None = None) -> None:
        self.project_root = project_root or os.getcwd()
        self._ignore_patterns: list[str] = []
        self._load_ignore_file()

    # ── Full evaluation ────────────────────────────────────────────────────

    def evaluate(self, tool_name: str, parameters: dict[str, Any]) -> list[RuleViolation]:
        """Check a tool call against all rules."""
        violations: list[RuleViolation] = []

        # Check command-based tools.
        command = parameters.get("command", "")
        if command:
            violations.extend(self.evaluate_command(command))

        # Check path-based tools.
        for key in ("path", "source", "destination", "target"):
            path = parameters.get(key, "")
            if path:
                violations.extend(self.evaluate_path(path))
                violations.extend(self._check_ignore(path))

        # Check paths array.
        paths = parameters.get("paths", [])
        if isinstance(paths, list):
            for p in paths:
                if isinstance(p, str):
                    violations.extend(self.evaluate_path(p))
                    violations.extend(self._check_ignore(p))

        return violations

    def evaluate_command(self, command: str) -> list[RuleViolation]:
        """Check a shell command against block/warn rules."""
        violations: list[RuleViolation] = []

        for rule in _BLOCK_RULES:
            if rule.pattern and re.search(rule.pattern, command, re.IGNORECASE):
                violations.append(RuleViolation(
                    rule_id=rule.id,
                    severity="block",
                    message=rule.message,
                    suggestion=rule.suggestion,
                ))

        for rule in _WARN_RULES:
            if rule.pattern and re.search(rule.pattern, command, re.IGNORECASE):
                violations.append(RuleViolation(
                    rule_id=rule.id,
                    severity="warn",
                    message=rule.message,
                    suggestion=rule.suggestion,
                ))

        return violations

    def evaluate_path(self, path: str) -> list[RuleViolation]:
        """Check a file path against block rules."""
        violations: list[RuleViolation] = []
        # Normalize path.
        expanded = os.path.expanduser(path).replace("\\", "/")

        for rule in _BLOCK_RULES:
            if rule.path_pattern:
                pattern_expanded = os.path.expanduser(rule.path_pattern).replace("\\", "/")
                if expanded.startswith(pattern_expanded) or expanded == pattern_expanded.rstrip("/"):
                    violations.append(RuleViolation(
                        rule_id=rule.id,
                        severity="block",
                        message=rule.message,
                        suggestion=rule.suggestion,
                    ))

        return violations

    # ── .nexcode-ignore ────────────────────────────────────────────────────

    def is_ignored(self, path: str) -> bool:
        """Check if a path matches .nexcode-ignore patterns."""
        return len(self._check_ignore(path)) > 0

    def _check_ignore(self, path: str) -> list[RuleViolation]:
        """Check path against .nexcode-ignore patterns."""
        if not self._ignore_patterns:
            return []

        # Make relative to project root.
        try:
            rel = os.path.relpath(path, self.project_root).replace("\\", "/")
        except ValueError:
            rel = path.replace("\\", "/")

        basename = os.path.basename(path)

        for pattern in self._ignore_patterns:
            # Match as glob-like pattern.
            if pattern.startswith("*"):
                # Extension match: *.pem → matches any .pem file.
                ext = pattern[1:]
                if basename.endswith(ext):
                    return [RuleViolation(
                        rule_id="IGN",
                        severity="block",
                        message=f"Path '{basename}' is listed in .nexcode-ignore",
                        suggestion="Remove from .nexcode-ignore to allow access",
                    )]
            elif pattern.endswith("/"):
                # Directory match.
                dir_name = pattern.rstrip("/")
                if rel.startswith(dir_name + "/") or rel == dir_name or f"/{dir_name}/" in f"/{rel}":
                    return [RuleViolation(
                        rule_id="IGN",
                        severity="block",
                        message=f"Path '{rel}' is in ignored directory '{pattern}'",
                        suggestion="Remove from .nexcode-ignore to allow access",
                    )]
            else:
                # Exact match or basename match.
                if rel == pattern or basename == pattern or rel.endswith("/" + pattern):
                    return [RuleViolation(
                        rule_id="IGN",
                        severity="block",
                        message=f"Path '{basename}' is listed in .nexcode-ignore",
                        suggestion="Remove from .nexcode-ignore to allow access",
                    )]

        return []

    def _load_ignore_file(self) -> None:
        """Load .nexcode-ignore from project root."""
        ignore_path = Path(self.project_root) / ".nexcode-ignore"
        if not ignore_path.exists():
            return
        try:
            content = ignore_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self._ignore_patterns.append(line)
        except OSError:
            pass

    def reload_ignore(self) -> None:
        """Reload .nexcode-ignore file."""
        self._ignore_patterns.clear()
        self._load_ignore_file()

    @property
    def ignore_patterns(self) -> list[str]:
        return list(self._ignore_patterns)

    # ── Helpers ────────────────────────────────────────────────────────────

    def has_blocks(self, violations: list[RuleViolation]) -> bool:
        return any(v.severity == "block" for v in violations)

    def has_warnings(self, violations: list[RuleViolation]) -> bool:
        return any(v.severity == "warn" for v in violations)
