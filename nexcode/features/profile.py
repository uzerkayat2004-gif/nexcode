"""
NexCode Performance Profiler Assistant
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

AI-powered profiling analysis and optimization suggestions.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table


@dataclass
class Hotspot:
    file: str = ""
    function: str = ""
    line: int = 0
    issue: str = ""
    severity: str = "medium"
    suggestion: str = ""


@dataclass
class ProfileReport:
    hotspots: list[Hotspot] = field(default_factory=list)
    summary: str = ""
    estimated_improvement: str = ""
    analysis_time_ms: int = 0


class PerformanceProfiler:
    """AI-powered performance analysis."""

    def __init__(self, ai_provider: Any = None, console: Console | None = None) -> None:
        self.ai = ai_provider
        self.console = console or Console()

    async def analyze(self, paths: list[str] | None = None) -> ProfileReport:
        """Analyze code for performance issues."""
        start = time.perf_counter()
        files = self._collect_files(paths)
        report = ProfileReport()

        for fpath in files[:15]:
            hotspots = await self._analyze_file(fpath)
            report.hotspots.extend(hotspots)

        report.analysis_time_ms = int((time.perf_counter() - start) * 1000)
        report.summary = f"Found {len(report.hotspots)} performance hotspots across {len(files)} files"
        return report

    async def suggest_optimizations(self, path: str) -> list[str]:
        """Get optimization suggestions for a file."""
        try:
            content = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return [f"Cannot read {path}"]

        if not self.ai:
            return ["AI provider needed for optimization suggestions"]

        try:
            resp = await self.ai.chat(
                messages=[{"role": "user", "content": f"Suggest performance optimizations:\n\n{content[:5000]}"}],
                system="You identify performance issues. List specific, actionable optimizations.",
            )
            text = getattr(resp, "content", "")
            return [line.strip() for line in text.splitlines() if line.strip().startswith("-")][:10]
        except Exception:
            return []

    async def profile_function(self, path: str, function_name: str) -> str:
        """Profile a specific function."""
        try:
            content = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return f"Cannot read {path}"

        if not self.ai:
            return "AI provider needed"

        try:
            resp = await self.ai.chat(
                messages=[{"role": "user", "content": (
                    f"Analyze the performance of function '{function_name}' in this code.\n"
                    f"Include time complexity, space complexity, and optimization suggestions.\n\n{content[:5000]}"
                )}],
                system="You analyze function performance. Include Big-O analysis.",
            )
            return getattr(resp, "content", "")
        except Exception:
            return "Analysis failed"

    def show_report(self, report: ProfileReport) -> None:
        """Display profiling report."""
        if not report.hotspots:
            self.console.print("  [green]✅ No performance issues detected[/]")
            return

        table = Table(title=" ⚡ Performance Hotspots ", border_style="yellow", show_lines=True)
        table.add_column("File", style="white")
        table.add_column("Function", style="cyan")
        table.add_column("Issue", style="yellow")
        table.add_column("Severity")
        table.add_column("Suggestion", style="green", max_width=30)

        severity_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
        for h in report.hotspots[:15]:
            icon = severity_icons.get(h.severity, "ℹ️")
            table.add_row(
                os.path.basename(h.file), h.function,
                h.issue, icon, h.suggestion[:30],
            )

        self.console.print(table)

    async def _analyze_file(self, path: str) -> list[Hotspot]:
        try:
            content = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        hotspots: list[Hotspot] = []

        # Heuristic checks.
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()

            # Nested loops.
            if "for " in stripped and line.count("    ") >= 2:
                hotspots.append(Hotspot(
                    file=path, line=i, function="",
                    issue="Nested loop — potential O(n²)",
                    severity="medium", suggestion="Consider using set/dict for lookups",
                ))

            # Global regex compile.
            if "re.compile" not in content and ("re.search" in stripped or "re.match" in stripped):
                hotspots.append(Hotspot(
                    file=path, line=i, function="",
                    issue="Uncompiled regex in hot path",
                    severity="low", suggestion="Pre-compile with re.compile()",
                ))

        # AI analysis.
        if self.ai and len(hotspots) < 3:
            try:
                resp = await self.ai.chat(
                    messages=[{"role": "user", "content": f"Find performance issues:\n{content[:4000]}"}],
                    system="Return: FUNCTION|LINE|ISSUE|SEVERITY|SUGGESTION, one per line.",
                )
                text = getattr(resp, "content", "")
                for line in text.splitlines():
                    parts = line.split("|")
                    if len(parts) >= 4:
                        hotspots.append(Hotspot(
                            file=path, function=parts[0].strip(),
                            line=int(parts[1].strip()) if parts[1].strip().isdigit() else 0,
                            issue=parts[2].strip(), severity=parts[3].strip().lower(),
                            suggestion=parts[4].strip() if len(parts) > 4 else "",
                        ))
            except Exception:
                pass

        return hotspots

    def _collect_files(self, paths: list[str] | None) -> list[str]:
        if paths:
            return [p for p in paths if os.path.isfile(p)]
        exts = {".py", ".js", ".ts", ".go", ".rs"}
        result: list[str] = []
        for root, _, files in os.walk(os.getcwd()):
            if any(d in root for d in [".git", "node_modules", "__pycache__", ".venv"]):
                continue
            for f in files:
                if Path(f).suffix in exts:
                    result.append(os.path.join(root, f))
        return result[:30]
