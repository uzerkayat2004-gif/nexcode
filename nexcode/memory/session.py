"""
NexCode Session Manager
~~~~~~~~~~~~~~~~~~~~~~~~

Manages active and past sessions — everything that happens
in one NexCode run.  Handles lifecycle, AI summaries,
persistence, and markdown export.
"""

from __future__ import annotations

import hashlib
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

_SESSIONS_BASE = Path.home() / ".nexcode" / "sessions"


# ---------------------------------------------------------------------------
# Session dataclass
# ---------------------------------------------------------------------------

@dataclass
class Session:
    """Record of a single NexCode session."""

    id: str
    started_at: datetime
    ended_at: datetime | None = None
    project_path: str = ""
    project_name: str = ""
    model_used: str = ""
    provider_used: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tasks_completed: int = 0
    tools_called: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    files_modified: list[str] = field(default_factory=list)
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        data["ended_at"] = self.ended_at.isoformat() if self.ended_at else None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        data = dict(data)  # shallow copy
        data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("ended_at"):
            data["ended_at"] = datetime.fromisoformat(data["ended_at"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @property
    def duration_display(self) -> str:
        end = self.ended_at or datetime.now(UTC)
        delta = end - self.started_at
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s"
        if secs < 3600:
            return f"{secs // 60}m {secs % 60}s"
        return f"{secs // 3600}h {(secs % 3600) // 60}m"


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

class SessionManager:
    """
    Manages NexCode session lifecycle.

    Sessions are stored per-project under ~/.nexcode/sessions/<hash>/.
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self, project_path: str, model: str = "", provider: str = "") -> Session:
        """Start a new session."""
        now = datetime.now(UTC)
        session = Session(
            id=f"ses_{now.strftime('%Y%m%d_%H%M%S')}",
            started_at=now,
            project_path=project_path,
            project_name=Path(project_path).name,
            model_used=model,
            provider_used=provider,
        )
        return session

    def save(self, session: Session) -> None:
        """Save current session state to disk."""
        project_hash = _hash_path(session.project_path)
        session_dir = _SESSIONS_BASE / project_hash
        session_dir.mkdir(parents=True, exist_ok=True)

        path = session_dir / f"{session.id}.json"
        try:
            path.write_text(
                json.dumps(session.to_dict(), default=str, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    async def end(self, session: Session, ai_provider: Any = None) -> None:
        """End session: set timestamp, generate AI summary, save."""
        session.ended_at = datetime.now(UTC)

        # Generate AI summary if provider available.
        if ai_provider and session.messages:
            try:
                summary_text = self._build_summary_prompt(session)
                response = await ai_provider.chat(
                    messages=[{"role": "user", "content": summary_text}],
                    system="Summarize in 1-2 sentences what was accomplished.",
                )
                session.summary = getattr(response, "content", str(response))
            except Exception:
                session.summary = f"{session.tasks_completed} tasks, {session.tools_called} tool calls"

        self.save(session)

    # ── Resume ─────────────────────────────────────────────────────────────

    def resume(self, session_id: str, project_path: str | None = None) -> Session | None:
        """Resume a previous session by ID."""
        # Search across all project dirs if no project specified.
        search_dirs: list[Path] = []
        if project_path:
            search_dirs.append(_SESSIONS_BASE / _hash_path(project_path))
        elif _SESSIONS_BASE.exists():
            search_dirs = list(_SESSIONS_BASE.iterdir())

        for d in search_dirs:
            path = d / f"{session_id}.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    return Session.from_dict(data)
                except (json.JSONDecodeError, OSError):
                    return None
        return None

    # ── Listing ────────────────────────────────────────────────────────────

    def list_sessions(
        self,
        project_path: str | None = None,
        limit: int = 20,
    ) -> list[Session]:
        """List past sessions, newest first."""
        if project_path:
            search_dir = _SESSIONS_BASE / _hash_path(project_path)
            if not search_dir.exists():
                return []
            files = sorted(search_dir.glob("ses_*.json"), reverse=True)
        elif _SESSIONS_BASE.exists():
            files = sorted(_SESSIONS_BASE.rglob("ses_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        else:
            return []

        sessions: list[Session] = []
        for f in files[:limit]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append(Session.from_dict(data))
            except (json.JSONDecodeError, OSError, TypeError):
                continue
        return sessions

    def show_sessions(self, sessions: list[Session]) -> None:
        """Display sessions in a Rich table."""
        if not sessions:
            self.console.print("  [dim]No sessions found.[/dim]")
            return

        project_name = sessions[0].project_name if sessions else "Unknown"
        table = Table(
            title=f"📚 Session History — {project_name}",
            title_style="bold white",
            border_style="bright_black",
            show_lines=True,
        )
        table.add_column("Session", min_width=20)
        table.add_column("Date", min_width=12)
        table.add_column("Tasks", min_width=6)
        table.add_column("Cost", min_width=8)
        table.add_column("Summary", max_width=30)

        for s in sessions:
            age = _relative_time(s.started_at)
            cost = f"${s.cost_usd:.3f}" if s.cost_usd else "—"
            summary = (s.summary or "—")[:30]
            table.add_row(s.id, age, str(s.tasks_completed), cost, summary)

        self.console.print()
        self.console.print(table)
        self.console.print()

    # ── Get / Delete ───────────────────────────────────────────────────────

    def get(self, session_id: str) -> Session | None:
        return self.resume(session_id)

    def delete(self, session_id: str) -> bool:
        """Delete a session by ID."""
        if not _SESSIONS_BASE.exists():
            return False
        for path in _SESSIONS_BASE.rglob(f"{session_id}.json"):
            path.unlink()
            return True
        return False

    # ── Export ──────────────────────────────────────────────────────────────

    def export(self, session_id: str, output_path: str) -> bool:
        """Export a session as a markdown report."""
        session = self.get(session_id)
        if not session:
            return False

        md = self._session_to_markdown(session)
        Path(output_path).write_text(md, encoding="utf-8")
        return True

    # ── Internal ───────────────────────────────────────────────────────────

    def _build_summary_prompt(self, session: Session) -> str:
        parts = [f"Summarize this NexCode session for project '{session.project_name}':\n"]
        for msg in session.messages[-20:]:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(str(b.get("text", b.get("content", ""))) for b in content if isinstance(b, dict))
            parts.append(f"[{role}]: {str(content)[:200]}")
        return "\n".join(parts)

    def _session_to_markdown(self, session: Session) -> str:
        lines = [
            "# NexCode Session Report",
            "",
            f"**Session:** {session.id}",
            f"**Project:** {session.project_name}",
            f"**Date:** {session.started_at.isoformat()}",
            f"**Duration:** {session.duration_display}",
            f"**Model:** {session.model_used}",
            f"**Tasks:** {session.tasks_completed}",
            f"**Cost:** ${session.cost_usd:.4f}",
            "",
        ]
        if session.summary:
            lines.append(f"## Summary\n{session.summary}\n")
        if session.files_modified:
            lines.append("## Files Modified")
            for f in session.files_modified:
                lines.append(f"- `{f}`")
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_path(path: str) -> str:
    """Hash a project path into a short directory name."""
    return hashlib.md5(path.encode()).hexdigest()[:12]


def _relative_time(dt: datetime) -> str:
    now = datetime.now(UTC)
    diff = now - dt
    secs = int(diff.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    days = secs // 86400
    if days == 1:
        return "yesterday"
    return f"{days}d ago"
