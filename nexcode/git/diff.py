"""
NexCode Git Diff Parser & Display
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Parses raw git diff output into structured objects and displays
them as beautifully formatted Rich panels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DiffLine:
    """A single line in a diff hunk."""

    content: str
    type: str  # "added", "removed", "context"


@dataclass
class DiffHunk:
    """A contiguous block of changes within a file."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header: str  # e.g. "@@ -23,7 +23,15 @@ def initialize"
    lines: list[DiffLine] = field(default_factory=list)


@dataclass
class FileDiff:
    """Diff for a single file."""

    path: str
    old_path: str | None = None   # for renames
    change_type: str = "modified"  # modified, added, deleted, renamed
    insertions: int = 0
    deletions: int = 0
    hunks: list[DiffHunk] = field(default_factory=list)


@dataclass
class DiffSummary:
    """High-level summary of a diff."""

    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    files: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DiffDisplay
# ---------------------------------------------------------------------------

class DiffDisplay:
    """Parse and display Git diffs with Rich formatting."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    # ── Parsing ────────────────────────────────────────────────────────────

    def parse(self, raw_diff: str) -> list[FileDiff]:
        """Parse raw git diff output into structured ``FileDiff`` objects."""
        if not raw_diff.strip():
            return []

        files: list[FileDiff] = []
        current_file: FileDiff | None = None
        current_hunk: DiffHunk | None = None

        for line in raw_diff.splitlines():

            # New file header: "diff --git a/path b/path"
            diff_match = re.match(r"^diff --git a/(.*) b/(.*)", line)
            if diff_match:
                if current_file:
                    files.append(current_file)
                old_path = diff_match.group(1)
                new_path = diff_match.group(2)
                current_file = FileDiff(
                    path=new_path,
                    old_path=old_path if old_path != new_path else None,
                )
                if old_path != new_path:
                    current_file.change_type = "renamed"
                current_hunk = None
                continue

            if not current_file:
                continue

            # Detect change type from mode lines.
            if line.startswith("new file"):
                current_file.change_type = "added"
                continue
            if line.startswith("deleted file"):
                current_file.change_type = "deleted"
                continue

            # Hunk header: "@@ -old_start,old_count +new_start,new_count @@"
            hunk_match = re.match(
                r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", line
            )
            if hunk_match:
                current_hunk = DiffHunk(
                    old_start=int(hunk_match.group(1)),
                    old_count=int(hunk_match.group(2) or 1),
                    new_start=int(hunk_match.group(3)),
                    new_count=int(hunk_match.group(4) or 1),
                    header=line,
                )
                if current_file:
                    current_file.hunks.append(current_hunk)
                continue

            # Diff content lines.
            if current_hunk is not None:
                if line.startswith("+"):
                    current_hunk.lines.append(DiffLine(content=line[1:], type="added"))
                    current_file.insertions += 1
                elif line.startswith("-"):
                    current_hunk.lines.append(DiffLine(content=line[1:], type="removed"))
                    current_file.deletions += 1
                elif line.startswith(" ") or line == "":
                    current_hunk.lines.append(DiffLine(content=line[1:] if line else "", type="context"))

        if current_file:
            files.append(current_file)

        return files

    # ── Display ────────────────────────────────────────────────────────────

    def show(self, diff: str | list[FileDiff], compact: bool = False) -> None:
        """Display a diff beautifully in the terminal."""
        if isinstance(diff, str):
            files = self.parse(diff)
        else:
            files = diff

        if not files:
            self.console.print("  [dim]No changes.[/dim]")
            return

        for file_diff in files:
            self._show_file_diff(file_diff, compact=compact)

    def _show_file_diff(self, fd: FileDiff, compact: bool = False) -> None:
        """Render a single file diff as a Rich panel."""
        # Build title.
        type_icon = {
            "modified": "Modified",
            "added": "Added",
            "deleted": "Deleted",
            "renamed": "Renamed",
        }
        title = f" {type_icon.get(fd.change_type, fd.change_type)}: {fd.path} "
        title += f"── +{fd.insertions} -{fd.deletions} "

        body = Text()
        for hunk in fd.hunks:
            body.append(hunk.header + "\n", style="yellow dim")

            if compact:
                # Show only added/removed lines in compact mode.
                for dl in hunk.lines:
                    if dl.type == "added":
                        body.append(f"+ {dl.content}\n", style="bright_green")
                    elif dl.type == "removed":
                        body.append(f"- {dl.content}\n", style="bright_red")
            else:
                for dl in hunk.lines:
                    if dl.type == "added":
                        body.append(f"+ {dl.content}\n", style="bright_green")
                    elif dl.type == "removed":
                        body.append(f"- {dl.content}\n", style="bright_red")
                    else:
                        body.append(f"  {dl.content}\n", style="bright_black")

        type_color = {
            "modified": "cyan",
            "added": "green",
            "deleted": "red",
            "renamed": "yellow",
        }

        self.console.print(
            Panel(
                body,
                title=title,
                title_align="left",
                border_style=type_color.get(fd.change_type, "white"),
                padding=(0, 1),
            )
        )

    # ── Summary ────────────────────────────────────────────────────────────

    def get_summary(self, diff: str) -> DiffSummary:
        """Get a high-level summary of a diff."""
        files = self.parse(diff)
        return DiffSummary(
            files_changed=len(files),
            insertions=sum(f.insertions for f in files),
            deletions=sum(f.deletions for f in files),
            files=[f.path for f in files],
        )

    def format_summary_text(self, diff: str) -> str:
        """Return a plain-text summary for AI output."""
        s = self.get_summary(diff)
        parts = []
        parts.append(f"{s.files_changed} file(s) changed")
        parts.append(f"+{s.insertions} insertions")
        parts.append(f"-{s.deletions} deletions")
        if s.files:
            parts.append("Files: " + ", ".join(s.files))
        return " | ".join(parts)
