"""
NexCode Commit History Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Display, search, and summarize git commit history
with beautiful Rich formatting and AI-friendly output.
"""

from __future__ import annotations

from datetime import UTC, datetime

from rich.console import Console
from rich.text import Text

from nexcode.git.engine import CommitInfo, GitEngine


class CommitHistory:
    """
    Manages commit history display, search, and AI summaries.
    """

    def __init__(self, engine: GitEngine, console: Console | None = None) -> None:
        self.engine = engine
        self.console = console or Console()

    # ── Log display ────────────────────────────────────────────────────────

    def show_log(self, commits: list[CommitInfo], show_graph: bool = True) -> str:
        """
        Display commit log in a graph-style format.

        Returns a plain-text version for AI output.
        """
        if not commits:
            self.console.print("  [dim]No commits found.[/dim]")
            return "No commits found."

        lines: list[str] = []
        for i, c in enumerate(commits):
            is_last = (i == len(commits) - 1)
            connector = "●" if show_graph else "•"
            pipe = "│" if not is_last else " "

            # First line: hash + message + relative time.
            age = _relative_time(c.date)
            header = Text()
            header.append(f"{connector} ", style="bold yellow")
            header.append(c.short_hash, style="bold cyan")
            header.append("  ", style="dim")
            header.append(c.message.splitlines()[0], style="white")
            header.append(f"  ({age})", style="bright_black")
            self.console.print(header)

            # Second line: author + stats.
            detail = Text()
            detail.append(f"{pipe}          ", style="dim yellow")
            detail.append(c.author, style="dim")
            if c.files_changed:
                detail.append(f" · {c.files_changed} file{'s' if c.files_changed != 1 else ''}", style="dim")
                detail.append(f" · +{c.insertions} -{c.deletions}", style="dim")
            self.console.print(detail)

            # Spacer.
            if not is_last:
                self.console.print(Text(f"{pipe}", style="dim yellow"))

            # Plain text for AI.
            lines.append(
                f"{c.short_hash} {c.message.splitlines()[0]} "
                f"({c.author}, {age}, {c.files_changed} files, "
                f"+{c.insertions} -{c.deletions})"
            )

        return "\n".join(lines)

    # ── Single commit detail ───────────────────────────────────────────────

    def show_commit(self, commit_hash: str) -> str:
        """Show detailed info for a specific commit."""
        try:
            # Find the commit in a broader search.
            repo = self.engine._get_repo()
            c = repo.commit(commit_hash)
            info = self.engine._commit_to_info(c)
        except Exception as exc:
            msg = f"Commit not found: {commit_hash} ({exc})"
            self.console.print(f"  [red]{msg}[/]")
            return msg

        header = Text()
        header.append("Commit: ", style="dim")
        header.append(info.hash, style="bold cyan")
        self.console.print(header)

        self.console.print(Text.assemble(
            ("Author: ", "dim"), (f"{info.author} <{info.email}>", "white"),
        ))
        self.console.print(Text.assemble(
            ("Date:   ", "dim"), (info.date.isoformat(), "white"),
        ))
        self.console.print()
        self.console.print(f"    {info.message}")
        self.console.print()
        self.console.print(Text.assemble(
            (f"    {info.files_changed} files changed, ", "dim"),
            (f"+{info.insertions}", "green"),
            (", ", "dim"),
            (f"-{info.deletions}", "red"),
        ))

        return (
            f"Commit {info.hash}\n"
            f"Author: {info.author} <{info.email}>\n"
            f"Date: {info.date.isoformat()}\n\n"
            f"    {info.message}\n\n"
            f"    {info.files_changed} files, +{info.insertions} -{info.deletions}"
        )

    # ── Search ─────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        by: str = "message",
        limit: int = 50,
    ) -> list[CommitInfo]:
        """Search commits by message, author, or file path."""
        all_commits = self.engine.get_log(limit=limit)
        query_lower = query.lower()

        results: list[CommitInfo] = []
        for c in all_commits:
            if by == "message" and query_lower in c.message.lower():
                results.append(c)
            elif by == "author" and query_lower in c.author.lower():
                results.append(c)

        return results

    # ── AI summary ─────────────────────────────────────────────────────────

    def get_summary_for_ai(self, limit: int = 10) -> str:
        """Generate a concise, AI-friendly summary of recent commits."""
        commits = self.engine.get_log(limit=limit)
        if not commits:
            return "No commits in this repository."

        lines = [f"Last {len(commits)} commits on branch '{self.engine.get_current_branch()}':\n"]
        for c in commits:
            age = _relative_time(c.date)
            lines.append(
                f"  {c.short_hash} | {c.message.splitlines()[0]:<50} "
                f"| {c.author} | {age} | {c.files_changed} files +{c.insertions} -{c.deletions}"
            )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _relative_time(dt: datetime) -> str:
    """Convert a datetime to a human-readable relative time string."""
    now = datetime.now(UTC)
    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        m = seconds // 60
        return f"{m} minute{'s' if m != 1 else ''} ago"
    elif seconds < 86400:
        h = seconds // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    elif seconds < 2592000:  # 30 days
        d = seconds // 86400
        return f"{d} day{'s' if d != 1 else ''} ago"
    else:
        m = seconds // 2592000
        return f"{m} month{'s' if m != 1 else ''} ago"
