"""
NexCode Audit Log
~~~~~~~~~~~~~~~~~~

Permanent record of every action NexCode takes.
Stored as JSONL files (one per day) under ~/.nexcode/audit/.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AUDIT_DIR = Path.home() / ".nexcode" / "audit"


# ---------------------------------------------------------------------------
# AuditEntry
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """A single entry in the audit log."""

    id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    session_id: str = ""
    tool_name: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    permission_decision: str = ""    # "auto", "user_approved", "user_denied", "blocked"
    result: str = ""                 # "success", "failed", "skipped"
    files_affected: list[str] = field(default_factory=list)
    risk_level: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        # Truncate large parameters for storage.
        for key in list(data.get("parameters", {}).keys()):
            val = str(data["parameters"][key])
            if len(val) > 500:
                data["parameters"][key] = val[:500] + "..."
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEntry:
        data = dict(data)
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

class AuditLog:
    """
    Persistent audit log.  Every tool execution is logged as a
    JSONL entry.  One file per day for easy rotation and cleanup.
    """

    def __init__(self, session_id: str = "", console: Console | None = None) -> None:
        self.session_id = session_id
        self.console = console or Console()
        _AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Write ──────────────────────────────────────────────────────────────

    def log(self, entry: AuditEntry) -> None:
        """Append an entry to today's audit log."""
        if not entry.session_id:
            entry.session_id = self.session_id

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        path = _AUDIT_DIR / f"audit_{today}.jsonl"

        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")
        except OSError:
            pass

    # ── Read ───────────────────────────────────────────────────────────────

    def get_recent(
        self,
        limit: int = 50,
        tool_filter: str | None = None,
        risk_filter: str | None = None,
    ) -> list[AuditEntry]:
        """Read recent entries across day files."""
        entries: list[AuditEntry] = []
        files = sorted(_AUDIT_DIR.glob("audit_*.jsonl"), reverse=True)

        for f in files[:7]:  # Last 7 days max.
            try:
                for line in reversed(f.read_text(encoding="utf-8").strip().splitlines()):
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        entry = AuditEntry.from_dict(data)

                        if tool_filter and entry.tool_name != tool_filter:
                            continue
                        if risk_filter and entry.risk_level != risk_filter:
                            continue

                        entries.append(entry)
                        if len(entries) >= limit:
                            return entries
                    except (json.JSONDecodeError, TypeError):
                        continue
            except OSError:
                continue

        return entries

    # ── Display ────────────────────────────────────────────────────────────

    def show(self, limit: int = 20) -> None:
        """Display audit log in a Rich table."""
        entries = self.get_recent(limit)

        if not entries:
            self.console.print("  [dim]No audit entries.[/dim]")
            return

        table = Table(
            title="📋 Audit Log — Recent",
            title_style="bold white",
            border_style="bright_black",
            show_lines=True,
        )
        table.add_column("Time", width=10)
        table.add_column("Tool", min_width=16)
        table.add_column("Risk", width=8)
        table.add_column("Decision", min_width=10)
        table.add_column("Result", min_width=10)

        risk_colors = {
            "safe": "green", "low": "cyan", "medium": "yellow",
            "high": "red", "critical": "bright_red",
        }
        result_icons = {
            "success": "✅ success", "failed": "❌ failed",
            "skipped": "⛔ skipped", "blocked": "🛑 blocked",
        }

        for e in entries:
            t = e.timestamp.strftime("%H:%M:%S") if isinstance(e.timestamp, datetime) else str(e.timestamp)[:8]
            risk_color = risk_colors.get(e.risk_level, "white")
            result_display = result_icons.get(e.result, e.result)

            table.add_row(
                t,
                e.tool_name,
                f"[{risk_color}]{e.risk_level}[/]",
                e.permission_decision,
                result_display,
            )

        self.console.print()
        self.console.print(table)
        self.console.print()

    # ── File history ───────────────────────────────────────────────────────

    def get_session_modified_files(self) -> list[str]:
        """Get all files modified in current session."""
        entries = self.get_recent(limit=500)
        files: list[str] = []
        for e in entries:
            if e.session_id == self.session_id:
                for f in e.files_affected:
                    if f not in files:
                        files.append(f)
        return files

    def get_file_history(self, path: str) -> list[AuditEntry]:
        """Get full audit trail for a specific file."""
        all_entries = self.get_recent(limit=500)
        return [e for e in all_entries if path in e.files_affected]

    # ── Export ─────────────────────────────────────────────────────────────

    def export(self, output_path: str) -> None:
        """Export all audit entries as a single JSON file."""
        entries = self.get_recent(limit=10000)
        data = [e.to_dict() for e in entries]
        Path(output_path).write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    # ── Cleanup ────────────────────────────────────────────────────────────

    def cleanup(self, keep_days: int = 30) -> int:
        """Delete audit files older than keep_days. Returns count deleted."""
        cutoff = datetime.now(UTC).timestamp() - (keep_days * 86400)
        deleted = 0
        for f in _AUDIT_DIR.glob("audit_*.jsonl"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        return deleted

    @property
    def total_entries_today(self) -> int:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        path = _AUDIT_DIR / f"audit_{today}.jsonl"
        if not path.exists():
            return 0
        try:
            return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        except OSError:
            return 0
