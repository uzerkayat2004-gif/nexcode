"""
NexCode Timeline Visualizer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Beautiful Rich-formatted timeline of checkpoints
and storage statistics dashboard.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from nexcode.checkpoints.manager import Checkpoint
from nexcode.checkpoints.storage import CheckpointStorage


class TimelineVisualizer:
    """
    Rich timeline display for checkpoints.
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    # ── Full timeline ──────────────────────────────────────────────────────

    def show(
        self,
        checkpoints: list[Checkpoint],
        highlight_id: str | None = None,
    ) -> None:
        """Show full checkpoint timeline."""
        if not checkpoints:
            self.console.print("  [dim]No checkpoints yet[/]")
            return

        body = Text()
        body.append("\n  NOW ", style="bold green")
        body.append("─" * 45, style="dim")
        body.append(" PAST\n\n", style="bold dim")

        body.append("  ● ", style="bold green")
        body.append("current state\n", style="green")

        for cp in checkpoints[:30]:
            age = _rel_time(cp.timestamp)
            is_highlight = cp.id == highlight_id
            dot_style = "bold cyan" if is_highlight else "bold white"
            tag_str = ""
            if cp.tags:
                tag_str = f"  [tagged: {', '.join(cp.tags)}]"

            body.append("  │\n", style="dim")
            body.append("  ● ", style=dot_style)

            short_id = cp.id.split("_")[-1] if "_" in cp.id else cp.id[:8]
            body.append(f"ckpt_{short_id}", style="cyan" if is_highlight else "white")
            body.append(f"  ({age})", style="dim")
            body.append(f"  {cp.tool_name}", style="yellow")
            if tag_str:
                body.append(tag_str, style="green")
            body.append("\n", style="white")

            body.append(f"  │            ", style="dim")
            body.append(f'"{cp.description[:50]}"\n', style="dim")

            file_count = len(cp.files)
            icon = "📁" if cp.tool_name == "snapshot" else "📝"
            body.append(f"  │            {icon} {file_count} file{'s' if file_count != 1 else ''}\n", style="dim")

        body.append("\n")

        self.console.print(Panel(
            body,
            title=" ⏱  Checkpoint Timeline ",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        ))

    # ── File timeline ──────────────────────────────────────────────────────

    def show_file_timeline(self, path: str, checkpoints: list[Checkpoint]) -> None:
        """Show timeline for a specific file."""
        basename = os.path.basename(path)
        relevant = [cp for cp in checkpoints if any(f.path == path or f.path.endswith(basename) for f in cp.files)]

        if not relevant:
            self.console.print(f"  [dim]No checkpoints for {path}[/]")
            return

        body = Text()
        body.append(f"\n  File: {path}\n\n", style="bold")

        for cp in relevant[:20]:
            age = _rel_time(cp.timestamp)
            body.append("  ● ", style="bold cyan")
            body.append(f"{cp.id[-4:]}", style="cyan")
            body.append(f"  {age:<10}", style="dim")
            body.append(f"  {cp.tool_name}", style="yellow")
            body.append(f'  "{cp.description[:40]}"\n', style="dim")

        self.console.print(Panel(
            body,
            title=f" 📄 {basename} History ",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        ))

    # ── Interactive ────────────────────────────────────────────────────────

    async def interactive(self, checkpoints: list[Checkpoint]) -> Checkpoint | None:
        """Interactive timeline — user picks a checkpoint."""
        if not checkpoints:
            self.console.print("  [dim]No checkpoints[/]")
            return None

        self.show(checkpoints)
        self.console.print("  [r] Restore selected  [d] View diff  [t] Tag  [x] Delete")

        try:
            idx_str = input("  Enter checkpoint number (1-based) › ").strip()
            idx = int(idx_str) - 1
            if 0 <= idx < len(checkpoints):
                return checkpoints[idx]
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
        return None

    # ── Storage stats ──────────────────────────────────────────────────────

    def show_storage_stats(self, storage: CheckpointStorage) -> None:
        """Show checkpoint storage statistics."""
        checkpoints = storage.list_checkpoints()
        total_bytes = storage.get_size_bytes()
        obj_count = storage.get_object_count()
        snapshot_count = sum(1 for cp in checkpoints if cp.tool_name == "snapshot")

        # Estimate raw size (sum of all file sizes across all checkpoints).
        raw_bytes = sum(f.size_bytes for cp in checkpoints for f in cp.files)
        dedup_pct = ((raw_bytes - total_bytes) / max(raw_bytes, 1)) * 100 if raw_bytes > 0 else 0

        body = Text()
        body.append(f"  Total checkpoints:    {len(checkpoints)}\n", style="white")
        body.append(f"  Full snapshots:       {snapshot_count}\n", style="white")
        body.append(f"  Unique files stored:  {obj_count}\n", style="white")
        body.append(f"  Raw size:             {_fmt_size(raw_bytes)}\n", style="white")
        body.append(
            f"  Deduplicated size:    {_fmt_size(total_bytes)}  ({dedup_pct:.0f}% saved)\n",
            style="green" if dedup_pct > 0 else "white",
        )
        body.append(f"  Location: {storage.base}\n", style="dim")

        self.console.print(Panel(
            body,
            title=" 💾 Checkpoint Storage ",
            title_align="left",
            border_style="blue",
            padding=(0, 1),
        ))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rel_time(dt: Any) -> str:
    if not isinstance(dt, datetime):
        return str(dt)
    now = datetime.now(timezone.utc)
    secs = int((now - dt).total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _fmt_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b / (1024 * 1024):.1f} MB"
