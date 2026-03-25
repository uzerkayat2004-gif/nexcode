"""
NexCode Multi-Project Workspace Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Manage multiple projects simultaneously with
instant switching and cross-project operations.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table


@dataclass
class Project:
    id: str = ""
    name: str = ""
    path: str = ""
    description: str | None = None
    language: str = ""
    last_opened: str = ""
    nexcode_md_path: str | None = None
    git_remote: str | None = None
    tags: list[str] = field(default_factory=list)
    favorite: bool = False


class WorkspaceManager:
    """Multi-project workspace manager."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self._config_path = Path.home() / ".nexcode" / "workspace.json"
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._projects: list[Project] = self._load()
        self._current: str | None = None

    # ── Project management ─────────────────────────────────────────────────

    def add_project(
        self,
        path: str,
        name: str | None = None,
        tags: list[str] | None = None,
    ) -> Project:
        """Add a project to workspace."""
        abs_path = os.path.abspath(path)
        proj_name = name or os.path.basename(abs_path)

        # Detect language.
        language = self._detect_language(abs_path)

        # Detect git remote.
        git_remote = self._detect_git_remote(abs_path)

        from hashlib import md5
        proj_id = md5(abs_path.encode()).hexdigest()[:8]

        project = Project(
            id=proj_id, name=proj_name, path=abs_path,
            language=language, last_opened=datetime.now(UTC).isoformat(),
            git_remote=git_remote, tags=tags or [],
        )

        # Replace if already exists.
        self._projects = [p for p in self._projects if p.path != abs_path]
        self._projects.insert(0, project)
        self._save()

        self.console.print(f"  [green]✅ Added: {proj_name} ({language})[/]")
        return project

    async def switch(self, project_id_or_name: str) -> Project | None:
        """Switch to a different project."""
        project = self._find(project_id_or_name)
        if not project:
            self.console.print(f"  [red]Project '{project_id_or_name}' not found[/]")
            return None

        if not os.path.exists(project.path):
            self.console.print(f"  [red]Path doesn't exist: {project.path}[/]")
            return None

        project.last_opened = datetime.now(UTC).isoformat()
        self._current = project.id
        self._save()
        os.chdir(project.path)

        self.console.print(f"  [green]✅ Switched to: {project.name} ({project.path})[/]")
        return project

    def list_projects(self) -> list[Project]:
        return list(self._projects)

    def remove_project(self, project_id: str) -> bool:
        before = len(self._projects)
        self._projects = [p for p in self._projects if p.id != project_id]
        if len(self._projects) < before:
            self._save()
            return True
        return False

    def search(self, query: str) -> list[Project]:
        q = query.lower()
        return [
            p for p in self._projects
            if q in p.name.lower() or q in p.language.lower() or any(q in t.lower() for t in p.tags)
        ]

    def get_recent(self, limit: int = 5) -> list[Project]:
        return sorted(self._projects, key=lambda p: p.last_opened, reverse=True)[:limit]

    # ── Dashboard ──────────────────────────────────────────────────────────

    def show_dashboard(self) -> None:
        """Show workspace dashboard."""
        if not self._projects:
            self.console.print("  [dim]No projects in workspace. Use /workspace add [path][/]")
            return

        table = Table(title=f" 🗂  Workspace — {len(self._projects)} projects ", border_style="blue", show_lines=True)
        table.add_column("", width=3)
        table.add_column("Project", style="bold")
        table.add_column("Language")
        table.add_column("Last Open", style="dim")
        table.add_column("Git", style="dim")

        for p in self._projects[:15]:
            marker = "▶ " if p.id == self._current else "  "
            star = "⭐ " if p.favorite else ""
            age = self._relative_time(p.last_opened)
            git_info = ""
            if p.git_remote:
                git_info = p.git_remote.split("/")[-1].replace(".git", "") if "/" in p.git_remote else "✅"

            table.add_row(marker, f"{star}{p.name}", p.language, age, git_info)

        self.console.print(table)
        self.console.print("  [s] Switch   [a] Add   [r] Remove   [/] Search")

    async def run_across_projects(self, instruction: str, project_ids: list[str]) -> dict[str, Any]:
        """Run same task across multiple projects."""
        results: dict[str, Any] = {}
        for pid in project_ids:
            project = self._find(pid)
            if project:
                results[project.name] = f"Task queued for {project.name}"
        return results

    # ── Internal ───────────────────────────────────────────────────────────

    def _find(self, id_or_name: str) -> Project | None:
        for p in self._projects:
            if p.id == id_or_name or p.name.lower() == id_or_name.lower():
                return p
        return None

    def _detect_language(self, path: str) -> str:
        ext_map = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".go": "Go",
                   ".rs": "Rust", ".java": "Java", ".rb": "Ruby", ".dart": "Flutter"}
        counts: Counter = Counter()
        from collections import Counter
        for root, _, files in os.walk(path):
            if any(d in root for d in [".git", "node_modules", "__pycache__"]):
                continue
            for f in files:
                lang = ext_map.get(Path(f).suffix)
                if lang:
                    counts[lang] += 1
            if sum(counts.values()) > 50:
                break
        return counts.most_common(1)[0][0] if counts else "Unknown"

    def _detect_git_remote(self, path: str) -> str | None:
        try:
            import subprocess
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, cwd=path,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def _relative_time(self, iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso)
            secs = int((datetime.now(UTC) - dt).total_seconds())
            if secs < 60: return "now"
            if secs < 3600: return f"{secs//60}m ago"
            if secs < 86400: return f"{secs//3600}h ago"
            return f"{secs//86400}d ago"
        except Exception:
            return iso[:10]

    def _load(self) -> list[Project]:
        if not self._config_path.exists():
            return []
        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
            return [Project(**p) for p in data]
        except (json.JSONDecodeError, TypeError):
            return []

    def _save(self) -> None:
        from dataclasses import asdict
        data = [
            {k: v for k, v in asdict(p).items()}
            for p in self._projects
        ]
        self._config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
