"""
NexCode Project Memory
~~~~~~~~~~~~~~~~~~~~~~~

Deep per-project memory that builds up over time.
Auto-detects tech stack, tracks architecture, and
surfaces key files for the AI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from nexcode.memory.store import MemoryStore

# ---------------------------------------------------------------------------
# ProjectMemory dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProjectMemory:
    """Persistent memory for a specific project."""

    project_path: str = ""
    project_name: str = ""
    language: str | None = None
    framework: str | None = None
    package_manager: str | None = None
    test_framework: str | None = None
    database: str | None = None
    key_files: list[str] = field(default_factory=list)
    architecture_notes: str = ""
    coding_conventions: list[str] = field(default_factory=list)
    common_commands: list[str] = field(default_factory=list)
    team_members: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_sessions: int = 0
    total_tasks: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["last_updated"] = self.last_updated.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectMemory:
        data = dict(data)
        if isinstance(data.get("last_updated"), str):
            data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Stack detection mappings
# ---------------------------------------------------------------------------

_LANG_FILES: dict[str, str] = {
    "pyproject.toml": "Python", "setup.py": "Python", "requirements.txt": "Python",
    "package.json": "JavaScript/TypeScript", "tsconfig.json": "TypeScript",
    "Cargo.toml": "Rust", "go.mod": "Go", "pom.xml": "Java",
    "build.gradle": "Java/Kotlin", "Gemfile": "Ruby",
    "composer.json": "PHP", "mix.exs": "Elixir",
}

_FRAMEWORK_FILES: dict[str, str] = {
    "next.config.js": "Next.js", "next.config.ts": "Next.js",
    "nuxt.config.js": "Nuxt", "nuxt.config.ts": "Nuxt",
    "vite.config.ts": "Vite", "vite.config.js": "Vite",
    "angular.json": "Angular", "svelte.config.js": "SvelteKit",
    "astro.config.mjs": "Astro", "remix.config.js": "Remix",
    "manage.py": "Django", "app.py": "Flask/FastAPI",
}

_PKG_MANAGERS: dict[str, str] = {
    "uv.lock": "uv", "poetry.lock": "poetry", "Pipfile.lock": "pipenv",
    "yarn.lock": "yarn", "pnpm-lock.yaml": "pnpm",
    "package-lock.json": "npm", "bun.lockb": "bun",
    "Cargo.lock": "cargo", "go.sum": "go",
}

_TEST_MARKERS: dict[str, str] = {
    "pytest.ini": "pytest", "setup.cfg": "pytest",
    "jest.config.js": "Jest", "jest.config.ts": "Jest",
    "vitest.config.ts": "Vitest", ".rspec": "RSpec",
}


# ---------------------------------------------------------------------------
# ProjectMemoryManager
# ---------------------------------------------------------------------------

class ProjectMemoryManager:
    """
    Manages per-project memory: tech stack detection,
    architecture notes, key files, and coding conventions.
    """

    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()

    # ── Load / Create ──────────────────────────────────────────────────────

    def load_or_create(self, project_path: str) -> ProjectMemory:
        """Load existing project memory or create a new one."""
        key = self._project_key(project_path)
        data = self.store.load(key)
        if data and isinstance(data, dict):
            try:
                return ProjectMemory.from_dict(data)
            except (TypeError, KeyError):
                pass

        # Create new with auto-detection.
        pm = ProjectMemory(
            project_path=project_path,
            project_name=Path(project_path).name,
        )
        self._detect_stack(pm)
        self.save(pm)
        return pm

    def save(self, project: ProjectMemory) -> None:
        """Save project memory to store."""
        project.last_updated = datetime.now(UTC)
        key = self._project_key(project.project_path)
        self.store.save(key, project.to_dict())

    # ── Stack detection ────────────────────────────────────────────────────

    def _detect_stack(self, pm: ProjectMemory) -> None:
        """Auto-detect project technology stack from files."""
        root = Path(pm.project_path)
        if not root.exists():
            return

        files_present = set()
        try:
            for item in root.iterdir():
                files_present.add(item.name)
        except OSError:
            return

        # Language.
        for marker, lang in _LANG_FILES.items():
            if marker in files_present:
                pm.language = lang
                break

        # Framework.
        for marker, fw in _FRAMEWORK_FILES.items():
            if marker in files_present:
                pm.framework = fw
                break

        # Package manager.
        for marker, mgr in _PKG_MANAGERS.items():
            if marker in files_present:
                pm.package_manager = mgr
                break

        # Test framework.
        for marker, tf in _TEST_MARKERS.items():
            if marker in files_present:
                pm.test_framework = tf
                break

        # Detect from pyproject.toml for Python projects.
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8").lower()
                if "fastapi" in content:
                    pm.framework = "FastAPI"
                elif "django" in content:
                    pm.framework = "Django"
                elif "flask" in content:
                    pm.framework = "Flask"
                if "pytest" in content:
                    pm.test_framework = "pytest"
                if "sqlalchemy" in content:
                    pm.database = "SQLAlchemy"
                if "uv" not in (pm.package_manager or ""):
                    if "[tool.uv]" in content or "uv.lock" in files_present:
                        pm.package_manager = "uv"
            except OSError:
                pass

        # Key files detection.
        key_file_names = [
            "main.py", "app.py", "index.ts", "index.js",
            "config.py", "settings.py", "config.ts",
            "README.md", "NEXCODE.md", "CLAUDE.md",
        ]
        pm.key_files = [f for f in key_file_names if (root / f).exists()]

        # Team members from git.
        try:
            from nexcode.git.engine import GitEngine
            engine = GitEngine(pm.project_path)
            if engine.is_git_repo():
                commits = engine.get_log(limit=50)
                authors = list({c.author for c in commits})
                pm.team_members = authors[:10]
        except Exception:
            pass

    async def detect_stack(self, project_path: str, ai_provider: Any = None) -> ProjectMemory:
        """Full stack detection (with optional AI analysis)."""
        pm = self.load_or_create(project_path)
        self._detect_stack(pm)
        self.save(pm)
        return pm

    # ── Architecture summary ───────────────────────────────────────────────

    async def generate_architecture_summary(
        self,
        project_path: str,
        ai_provider: Any,
    ) -> str:
        """Generate an AI summary of the project architecture."""
        pm = self.load_or_create(project_path)

        # Gather info for AI.
        info_lines = [
            f"Project: {pm.project_name}",
            f"Language: {pm.language or 'unknown'}",
            f"Framework: {pm.framework or 'unknown'}",
            f"Package manager: {pm.package_manager or 'unknown'}",
        ]

        # Read key files for structure.
        root = Path(project_path)
        try:
            dirs = [d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]
            info_lines.append(f"Top-level directories: {', '.join(dirs[:15])}")
        except OSError:
            pass

        prompt = (
            "Based on this project info, write a 2-3 sentence architecture summary:\n\n"
            + "\n".join(info_lines)
        )

        try:
            response = await ai_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You are a software architect. Be concise.",
            )
            summary = getattr(response, "content", str(response))
            pm.architecture_notes = summary
            self.save(pm)
            return summary
        except Exception:
            return pm.architecture_notes or "Architecture not yet analyzed."

    # ── Key files ──────────────────────────────────────────────────────────

    def get_key_files(self, project: ProjectMemory) -> list[str]:
        """Return list of key files the AI should always read."""
        return project.key_files

    # ── Update after session ───────────────────────────────────────────────

    def update_after_session(self, project_path: str, tasks: int = 0) -> None:
        pm = self.load_or_create(project_path)
        pm.total_sessions += 1
        pm.total_tasks += tasks
        self.save(pm)

    # ── Dashboard display ──────────────────────────────────────────────────

    def show_dashboard(self, project: ProjectMemory, console: Console | None = None) -> None:
        """Display project memory as a Rich dashboard."""
        console = console or Console()

        body = Text()
        body.append(f"  Language:    {project.language or '—'}\n", style="white")
        body.append(f"  Framework:   {project.framework or '—'}\n", style="white")
        body.append(f"  Database:    {project.database or '—'}\n", style="white")
        body.append(f"  Tests:       {project.test_framework or '—'}\n", style="white")
        body.append(f"  Package Mgr: {project.package_manager or '—'}\n", style="white")

        if project.key_files:
            body.append("\n  Key Files:\n", style="bold")
            body.append(f"    📄 {', '.join(project.key_files)}\n", style="dim")

        if project.architecture_notes:
            body.append("\n  Architecture:\n", style="bold")
            body.append(f"    {project.architecture_notes[:200]}\n", style="dim")

        if project.team_members:
            body.append(f"\n  Team: {', '.join(project.team_members[:5])}\n", style="dim")

        from nexcode.memory.session import _relative_time
        age = _relative_time(project.last_updated)
        body.append(
            f"\n  Sessions: {project.total_sessions}  │  "
            f"Tasks: {project.total_tasks}  │  "
            f"Last: {age}\n",
            style="dim",
        )

        console.print(
            Panel(
                body,
                title=f" 🏗️  Project: {project.project_name} ",
                title_align="left",
                border_style="bright_blue",
                padding=(0, 1),
            )
        )

    # ── Internal ───────────────────────────────────────────────────────────

    def _project_key(self, path: str) -> str:
        import hashlib
        h = hashlib.md5(path.encode()).hexdigest()[:12]
        return f"projects/{h}"

    def __repr__(self) -> str:
        return "ProjectMemoryManager()"
