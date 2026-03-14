"""
NexCode Checkpoint Diff Viewer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shows what changed between checkpoints and current state,
with Rich-formatted restore preview panels.
"""

from __future__ import annotations

import difflib
import os
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from nexcode.checkpoints.manager import Checkpoint
from nexcode.checkpoints.storage import CheckpointStorage

# ---------------------------------------------------------------------------
# CheckpointSummary
# ---------------------------------------------------------------------------

@dataclass
class CheckpointSummary:
    """Summary of changes between a checkpoint and current state."""

    files_modified: list[str] = field(default_factory=list)
    files_added: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    total_insertions: int = 0
    total_deletions: int = 0
    is_identical: bool = False


# ---------------------------------------------------------------------------
# CheckpointDiff
# ---------------------------------------------------------------------------

class CheckpointDiff:
    """
    Diff viewer for checkpoint comparisons.
    """

    def __init__(
        self,
        storage: CheckpointStorage,
        project_root: str | None = None,
        console: Console | None = None,
    ) -> None:
        self.storage = storage
        self.project_root = project_root or os.getcwd()
        self.console = console or Console()

    # ── Diff vs current ────────────────────────────────────────────────────

    def show_vs_current(
        self,
        checkpoint: Checkpoint,
        paths: list[str] | None = None,
    ) -> None:
        """Show unified diff between checkpoint and current file state."""
        for cpf in checkpoint.files:
            if paths and cpf.path not in paths:
                continue

            abs_path = os.path.join(self.project_root, cpf.path)

            # Get checkpoint content.
            old_content = ""
            if cpf.existed_before and cpf.storage_key:
                old_content = self.storage.retrieve(cpf.storage_key) or ""

            # Get current content.
            new_content = ""
            if os.path.exists(abs_path):
                try:
                    new_content = Path(abs_path).read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    new_content = "<binary or unreadable>"

            if old_content == new_content:
                self.console.print(f"  [dim]📄 {cpf.path} — no change[/]")
                continue

            # Generate unified diff.
            old_lines = old_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            diff = difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"checkpoint: {cpf.path}",
                tofile=f"current: {cpf.path}",
            )

            diff_text = Text()
            for line in diff:
                line = line.rstrip("\n")
                if line.startswith("+++") or line.startswith("---"):
                    diff_text.append(line + "\n", style="bold white")
                elif line.startswith("@@"):
                    diff_text.append(line + "\n", style="cyan")
                elif line.startswith("+"):
                    diff_text.append(line + "\n", style="green")
                elif line.startswith("-"):
                    diff_text.append(line + "\n", style="red")
                else:
                    diff_text.append(line + "\n", style="dim")

            self.console.print(Panel(
                diff_text,
                title=f" {cpf.path} ",
                title_align="left",
                border_style="bright_black",
            ))

    # ── Diff between two checkpoints ───────────────────────────────────────

    def show_between(
        self,
        checkpoint_a: Checkpoint,
        checkpoint_b: Checkpoint,
    ) -> None:
        """Show diff between two checkpoints."""
        files_a = {f.path: f for f in checkpoint_a.files}
        files_b = {f.path: f for f in checkpoint_b.files}
        all_paths = sorted(set(files_a.keys()) | set(files_b.keys()))

        for path in all_paths:
            old = ""
            new = ""
            fa = files_a.get(path)
            fb = files_b.get(path)

            if fa and fa.storage_key:
                old = self.storage.retrieve(fa.storage_key) or ""
            if fb and fb.storage_key:
                new = self.storage.retrieve(fb.storage_key) or ""

            if old == new:
                continue

            diff = difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )

            diff_text = Text()
            for line in diff:
                line = line.rstrip("\n")
                if line.startswith("+"):
                    diff_text.append(line + "\n", style="green")
                elif line.startswith("-"):
                    diff_text.append(line + "\n", style="red")
                else:
                    diff_text.append(line + "\n", style="dim")

            self.console.print(Panel(diff_text, title=f" {path} ", border_style="bright_black"))

    # ── Summary ────────────────────────────────────────────────────────────

    def get_summary(self, checkpoint: Checkpoint) -> CheckpointSummary:
        """Get a summary of changes without full diff."""
        summary = CheckpointSummary()

        for cpf in checkpoint.files:
            abs_path = os.path.join(self.project_root, cpf.path)
            current_exists = os.path.exists(abs_path)

            if not cpf.existed_before:
                # File was created after checkpoint.
                if current_exists:
                    summary.files_added.append(cpf.path)
                continue

            if not current_exists:
                summary.files_deleted.append(cpf.path)
                continue

            # Compare content.
            try:
                current = Path(abs_path).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                summary.files_modified.append(cpf.path)
                continue

            old = self.storage.retrieve(cpf.storage_key) or ""
            if current != old:
                summary.files_modified.append(cpf.path)
                # Count lines.
                old_lines = old.splitlines()
                new_lines = current.splitlines()
                sm = difflib.SequenceMatcher(None, old_lines, new_lines)
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "replace":
                        summary.total_deletions += i2 - i1
                        summary.total_insertions += j2 - j1
                    elif tag == "delete":
                        summary.total_deletions += i2 - i1
                    elif tag == "insert":
                        summary.total_insertions += j2 - j1

        summary.is_identical = not (summary.files_modified or summary.files_added or summary.files_deleted)
        return summary

    # ── Show changed files ─────────────────────────────────────────────────

    def show_changed_files(self, checkpoint: Checkpoint) -> None:
        """Show which files differ between checkpoint and current."""
        summary = self.get_summary(checkpoint)
        if summary.is_identical:
            self.console.print("  [green]✅ No changes from checkpoint[/]")
            return
        for f in summary.files_modified:
            self.console.print(f"  [yellow]📝 {f}[/]")
        for f in summary.files_added:
            self.console.print(f"  [green]➕ {f}[/] (created after checkpoint)")
        for f in summary.files_deleted:
            self.console.print(f"  [red]🗑  {f}[/] (deleted after checkpoint)")

    # ── Restore preview ────────────────────────────────────────────────────

    def show_restore_preview(self, checkpoint: Checkpoint) -> None:
        """Show a Rich preview panel before restoring."""
        summary = self.get_summary(checkpoint)
        age = _relative_time(checkpoint.timestamp)

        body = Text()
        body.append(f"  Checkpoint: {checkpoint.id}\n", style="white")
        body.append(f'  Created:    {age} — "{checkpoint.description}"\n\n', style="dim")

        if summary.is_identical:
            body.append("  ✅ No changes — files are identical to checkpoint\n", style="green")
        else:
            body.append("  Files that will be restored:\n\n", style="bold")
            for f in summary.files_modified:
                body.append(f"  📝 {f}\n", style="yellow")
            for f in summary.files_added:
                body.append(f"  🗑  {f}  (will be DELETED — created after checkpoint)\n", style="red")
            for f in summary.files_deleted:
                body.append(f"  📄 {f}  (will be RECREATED)\n", style="green")

            if summary.total_insertions or summary.total_deletions:
                body.append(
                    f"\n  +{summary.total_insertions} -{summary.total_deletions} lines\n",
                    style="dim",
                )

        self.console.print(Panel(
            body,
            title=" ⏪ Restore Preview ",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        ))


def _relative_time(dt: Any) -> str:
    from datetime import datetime
    if not isinstance(dt, datetime):
        return str(dt)
    now = datetime.now(UTC)
    diff = now - dt
    secs = int(diff.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"
