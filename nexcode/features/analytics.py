"""
NexCode Project Analytics Dashboard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Code metrics, language stats, git stats, NexCode usage,
and Rich dashboard display.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "React JSX", ".tsx": "React TSX", ".go": "Go",
    ".rs": "Rust", ".java": "Java", ".rb": "Ruby", ".php": "PHP",
    ".css": "CSS", ".html": "HTML", ".sql": "SQL", ".sh": "Shell",
    ".c": "C", ".cpp": "C++", ".cs": "C#", ".swift": "Swift",
    ".kt": "Kotlin", ".dart": "Dart", ".r": "R", ".scala": "Scala",
}

LANG_ICONS: dict[str, str] = {
    "Python": "🐍", "JavaScript": "📜", "TypeScript": "📘",
    "Go": "🐹", "Rust": "🦀", "Java": "☕", "CSS": "🎨",
    "HTML": "🌐", "Ruby": "💎", "C": "⚙️", "C++": "⚙️",
}


@dataclass
class LanguageStats:
    language: str = ""
    files: int = 0
    lines: int = 0
    percentage: float = 0.0


@dataclass
class ProjectStats:
    total_files: int = 0
    total_lines: int = 0
    total_blank_lines: int = 0
    total_comment_lines: int = 0
    languages: dict[str, LanguageStats] = field(default_factory=dict)
    avg_function_length: float = 0.0
    avg_file_length: float = 0.0
    longest_file: str = ""
    most_complex_file: str = ""
    duplicate_code_pct: float = 0.0
    test_files: int = 0
    test_lines: int = 0
    estimated_coverage: float = 0.0
    total_dependencies: int = 0
    outdated_dependencies: int = 0
    vulnerable_dependencies: int = 0
    total_commits: int = 0
    contributors: list[str] = field(default_factory=list)
    most_changed_file: str = ""
    commit_frequency: float = 0.0
    total_ai_tasks: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    files_ai_modified: int = 0
    time_saved_estimate: str = ""


@dataclass
class UsageStats:
    sessions: int = 0
    tasks: int = 0
    tokens: int = 0
    cost: float = 0.0


class ProjectAnalytics:
    """Project analytics dashboard."""

    def __init__(self, project_root: str | None = None, console: Console | None = None) -> None:
        self.root = project_root or os.getcwd()
        self.console = console or Console()

    async def analyze(self) -> ProjectStats:
        """Analyze entire project."""
        stats = ProjectStats()
        lang_counter: Counter[str] = Counter()
        lang_lines: Counter[str] = Counter()
        max_lines = 0
        max_file = ""

        skip = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".nexcode"}

        for root, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in skip]
            for fname in files:
                ext = Path(fname).suffix
                lang = LANGUAGE_MAP.get(ext)
                if not lang:
                    continue

                fpath = os.path.join(root, fname)
                stats.total_files += 1
                lang_counter[lang] += 1

                try:
                    lines = Path(fpath).read_text(encoding="utf-8").splitlines()
                    lc = len(lines)
                    stats.total_lines += lc
                    lang_lines[lang] += lc

                    for line in lines:
                        stripped = line.strip()
                        if not stripped:
                            stats.total_blank_lines += 1
                        elif stripped.startswith(("#", "//", "/*", "*", "'")):
                            stats.total_comment_lines += 1

                    if lc > max_lines:
                        max_lines = lc
                        max_file = os.path.relpath(fpath, self.root)

                    # Test detection.
                    if "test" in fname.lower() or "spec" in fname.lower():
                        stats.test_files += 1
                        stats.test_lines += lc

                except (OSError, UnicodeDecodeError):
                    continue

        stats.longest_file = max_file
        stats.avg_file_length = stats.total_lines / max(stats.total_files, 1)

        # Language stats.
        for lang, count in lang_counter.most_common():
            stats.languages[lang] = LanguageStats(
                language=lang, files=count, lines=lang_lines[lang],
                percentage=round(lang_lines[lang] / max(stats.total_lines, 1) * 100, 1),
            )

        # Test coverage estimate.
        code_lines = stats.total_lines - stats.test_lines
        stats.estimated_coverage = round(stats.test_lines / max(code_lines, 1) * 100, 1) if stats.test_lines else 0

        # Git stats.
        self._collect_git_stats(stats)

        # Dependency count.
        stats.total_dependencies = self._count_dependencies()

        # Time saved estimate.
        stats.time_saved_estimate = f"~{stats.total_ai_tasks * 0.04:.1f} hours"

        return stats

    def show_dashboard(self, stats: ProjectStats) -> None:
        """Show full analytics dashboard."""
        project_name = os.path.basename(self.root)

        # Code & Tests.
        left = Text()
        left.append("  📁 Code\n", style="bold")
        left.append(f"  Files:      {stats.total_files:,}\n", style="white")
        left.append(f"  Lines:   {stats.total_lines:,}\n", style="white")
        left.append(f"  Languages:   {len(stats.languages)}\n\n", style="white")

        for lang, ls in list(stats.languages.items())[:5]:
            icon = LANG_ICONS.get(lang, "📄")
            left.append(f"  {icon} {lang:<12} {ls.percentage}%\n", style="white")

        right = Text()
        right.append("  🧪 Tests\n", style="bold")
        right.append(f"  Test files:  {stats.test_files}\n", style="white")
        right.append(f"  Test lines:  {stats.test_lines:,}\n", style="white")
        right.append(f"  Est. coverage: {stats.estimated_coverage}%\n\n", style="white")

        right.append("  🤖 NexCode Usage\n", style="bold")
        right.append(f"  Tasks run:    {stats.total_ai_tasks}\n", style="white")
        right.append(f"  Tokens used:  {stats.total_tokens_used:,}\n", style="white")
        right.append(f"  Cost:        ${stats.total_cost_usd:.2f}\n", style="white")
        right.append(f"  Time saved:  {stats.time_saved_estimate}\n", style="white")

        # Bottom: deps + git.
        bottom = Text()
        bottom.append("  📦 Dependencies          🌿 Git\n", style="bold")
        bottom.append(f"  Total:       {stats.total_dependencies:<10}", style="white")
        bottom.append(f"  Commits:     {stats.total_commits}\n", style="white")
        bottom.append(f"  Contributors:  {len(stats.contributors)}\n", style="white")

        self.console.print(Panel(
            left, title=f" 📊 Project Analytics — {project_name} ",
            title_align="left", border_style="blue", padding=(0, 1),
        ))
        self.console.print(Panel(right, border_style="blue", padding=(0, 1)))
        self.console.print(Panel(bottom, border_style="blue", padding=(0, 1)))

    def get_usage_stats(self) -> UsageStats:
        """NexCode usage stats."""
        return UsageStats()

    def _collect_git_stats(self, stats: ProjectStats) -> None:
        try:
            import subprocess
            result = subprocess.run(
                ["git", "log", "--oneline"], capture_output=True, text=True, cwd=self.root,
            )
            stats.total_commits = len(result.stdout.strip().splitlines()) if result.stdout else 0

            result2 = subprocess.run(
                ["git", "shortlog", "-s", "-n"], capture_output=True, text=True, cwd=self.root,
            )
            if result2.stdout:
                stats.contributors = [
                    line.strip().split("\t", 1)[-1] for line in result2.stdout.splitlines() if line.strip()
                ]
        except Exception:
            pass

    def _count_dependencies(self) -> int:
        count = 0
        for f in ["requirements.txt", "pyproject.toml", "package.json"]:
            fpath = os.path.join(self.root, f)
            if os.path.exists(fpath):
                try:
                    content = Path(fpath).read_text(encoding="utf-8")
                    count += content.count("==") + content.count(">=") + content.count('"dependencies"')
                except OSError:
                    pass
        return count
