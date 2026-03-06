"""
NexCode AI Code Review Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Automatic code review with severity levels, categories,
auto-fix, staged/diff review, and quality scoring.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

REVIEW_CATEGORIES: dict[str, list[str]] = {
    "bugs": [
        "null pointer dereference", "off-by-one errors", "unhandled exceptions",
        "race conditions", "infinite loops", "memory leaks", "incorrect type handling",
    ],
    "security": [
        "SQL injection", "XSS vulnerabilities", "hardcoded secrets",
        "insecure random", "path traversal", "command injection",
        "insecure deserialization", "missing auth checks", "exposed data in logs",
    ],
    "performance": [
        "N+1 queries", "missing indexes", "O(n²) where O(n) possible",
        "unnecessary re-renders", "blocking I/O in async", "large bundles", "missing caching",
    ],
    "maintainability": [
        "functions >50 lines", "too many parameters", "deep nesting",
        "magic numbers", "duplicate code", "missing type hints", "unclear names", "missing error handling",
    ],
    "test_coverage": [
        "untested public functions", "missing edge case tests",
        "no error path tests", "brittle assertions",
    ],
}


@dataclass
class CodeIssue:
    file: str = ""
    line_start: int = 0
    line_end: int = 0
    severity: str = "medium"
    category: str = "bugs"
    title: str = ""
    description: str = ""
    suggestion: str = ""
    code_before: str = ""
    code_after: str = ""
    auto_fixable: bool = False


@dataclass
class ReviewReport:
    files_reviewed: list[str] = field(default_factory=list)
    total_issues: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    score: int = 100
    issues: list[CodeIssue] = field(default_factory=list)
    summary: str = ""
    top_recommendations: list[str] = field(default_factory=list)
    review_time_ms: int = 0


@dataclass
class FixResult:
    files_fixed: list[str] = field(default_factory=list)
    issues_fixed: int = 0
    issues_skipped: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CodeReviewer
# ---------------------------------------------------------------------------

class CodeReviewer:
    """AI-powered code review engine."""

    def __init__(self, ai_provider: Any = None, console: Console | None = None) -> None:
        self.ai = ai_provider
        self.console = console or Console()

    async def review(
        self,
        paths: list[str] | str | None = None,
        focus: list[str] | None = None,
        severity_threshold: str = "low",
    ) -> ReviewReport:
        """Review files and return a structured report."""
        start = time.perf_counter()
        files = self._resolve_files(paths)
        report = ReviewReport(files_reviewed=files)

        for fpath in files[:30]:
            try:
                content = Path(fpath).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            issues = await self._review_file(fpath, content, focus)
            report.issues.extend(issues)

        self._score(report)
        report.review_time_ms = int((time.perf_counter() - start) * 1000)
        return report

    async def review_staged(self) -> ReviewReport:
        """Review only git staged changes."""
        try:
            from nexcode.git.engine import GitEngine
            engine = GitEngine()
            status = engine.get_status()
            return await self.review(status.staged_files)
        except Exception:
            return ReviewReport(summary="Git not available")

    async def review_diff(self, diff: str) -> ReviewReport:
        """Review a diff string."""
        report = ReviewReport()
        if self.ai:
            prompt = f"Review this code diff for bugs, security, and quality issues:\n\n{diff[:8000]}"
            issues = await self._parse_ai_review(prompt, "diff")
            report.issues.extend(issues)
        self._score(report)
        return report

    async def auto_fix(self, report: ReviewReport, severity_filter: str = "high") -> FixResult:
        """Auto-fix fixable issues at or above severity."""
        levels = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
        threshold = levels.get(severity_filter, 3)
        result = FixResult()

        for issue in report.issues:
            if not issue.auto_fixable:
                result.issues_skipped += 1
                continue
            if levels.get(issue.severity, 0) < threshold:
                result.issues_skipped += 1
                continue
            if issue.code_before and issue.code_after:
                try:
                    content = Path(issue.file).read_text(encoding="utf-8")
                    if issue.code_before in content:
                        content = content.replace(issue.code_before, issue.code_after, 1)
                        Path(issue.file).write_text(content, encoding="utf-8")
                        result.files_fixed.append(issue.file)
                        result.issues_fixed += 1
                except OSError as e:
                    result.errors.append(str(e))

        return result

    async def review_pr(self, pr_number: int) -> ReviewReport:
        """Review a PR (requires gh CLI)."""
        import asyncio, subprocess
        try:
            proc = await asyncio.create_subprocess_shell(
                f"gh pr diff {pr_number}", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            diff = stdout.decode(errors="replace")
            return await self.review_diff(diff)
        except Exception:
            return ReviewReport(summary=f"Cannot fetch PR #{pr_number}")

    def show_report(self, report: ReviewReport) -> None:
        """Display the review report."""
        body = Text()
        body.append(f"  Files reviewed: {len(report.files_reviewed)}   Issues: {report.total_issues}\n", style="white")
        body.append(f"  🔴 Critical: {report.critical}   🟠 High: {report.high}   ", style="white")
        body.append(f"🟡 Medium: {report.medium}   🔵 Low: {report.low}\n\n", style="white")

        severity_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "ℹ️"}
        for issue in report.issues[:20]:
            icon = severity_icons.get(issue.severity, "ℹ️")
            body.append(f"  {icon} {issue.severity.upper()} — {issue.category}\n", style="bold")
            body.append(f"  {issue.file}:{issue.line_start}\n", style="dim")
            body.append(f"  {issue.title}\n", style="white")
            if issue.code_before:
                body.append(f"  - {issue.code_before[:80]}\n", style="red")
            if issue.code_after:
                body.append(f"  + {issue.code_after[:80]}\n", style="green")
            fix_label = "  [a] Auto-fix" if issue.auto_fixable else ""
            body.append(f"  {fix_label}\n\n", style="cyan")

        self.console.print(Panel(
            body, title=f" 🔍 Code Review Report    Score: {report.score}/100 ",
            title_align="left", border_style="cyan", padding=(0, 1),
        ))

    # ── Internal ───────────────────────────────────────────────────────────

    async def _review_file(self, path: str, content: str, focus: list[str] | None) -> list[CodeIssue]:
        if not self.ai:
            return []
        categories = ", ".join(focus) if focus else "bugs, security, performance, maintainability"
        prompt = (
            f"Review this code for issues in: {categories}\n"
            f"File: {path}\n\n{content[:6000]}\n\n"
            "For each issue return: SEVERITY|CATEGORY|LINE|TITLE|DESCRIPTION|SUGGESTION\n"
            "One issue per line."
        )
        return await self._parse_ai_review(prompt, path)

    async def _parse_ai_review(self, prompt: str, default_file: str) -> list[CodeIssue]:
        try:
            resp = await self.ai.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You are a strict code reviewer. Return issues in the exact format requested.",
            )
            text = getattr(resp, "content", str(resp))
            issues: list[CodeIssue] = []
            for line in text.splitlines():
                parts = line.split("|")
                if len(parts) >= 4:
                    issues.append(CodeIssue(
                        file=default_file, severity=parts[0].strip().lower(),
                        category=parts[1].strip().lower(),
                        line_start=int(parts[2].strip()) if parts[2].strip().isdigit() else 0,
                        title=parts[3].strip(),
                        description=parts[4].strip() if len(parts) > 4 else "",
                        suggestion=parts[5].strip() if len(parts) > 5 else "",
                    ))
            return issues
        except Exception:
            return []

    def _score(self, report: ReviewReport) -> None:
        for issue in report.issues:
            if issue.severity == "critical": report.critical += 1
            elif issue.severity == "high": report.high += 1
            elif issue.severity == "medium": report.medium += 1
            else: report.low += 1
        report.total_issues = len(report.issues)
        deductions = report.critical * 15 + report.high * 8 + report.medium * 3 + report.low * 1
        report.score = max(0, 100 - deductions)

    def _resolve_files(self, paths: list[str] | str | None) -> list[str]:
        if isinstance(paths, str):
            paths = [paths]
        if paths:
            return [p for p in paths if os.path.isfile(p)]
        exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java"}
        result: list[str] = []
        for root, _, files in os.walk(os.getcwd()):
            if any(d in root for d in [".git", "node_modules", "__pycache__", ".venv"]):
                continue
            for f in files:
                if Path(f).suffix in exts:
                    result.append(os.path.join(root, f))
        return result[:50]
