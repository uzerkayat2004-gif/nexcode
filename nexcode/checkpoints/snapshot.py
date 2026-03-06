"""
NexCode Snapshot & Task Undo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Full project snapshots and grouped task undo.
"""

from __future__ import annotations

import fnmatch
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from nexcode.checkpoints.manager import (
    Checkpoint,
    CheckpointFile,
    RestoreResult,
)
from nexcode.checkpoints.storage import CheckpointStorage


# ---------------------------------------------------------------------------
# Default excludes
# ---------------------------------------------------------------------------

DEFAULT_EXCLUDES: list[str] = [
    ".git/", "__pycache__/", "node_modules/", ".venv/",
    "*.pyc", ".nexcode/", "dist/", "build/",
    "*.egg-info/", ".tox/", ".mypy_cache/",
    ".pytest_cache/", "*.so", "*.dll",
]


# ---------------------------------------------------------------------------
# SnapshotManager
# ---------------------------------------------------------------------------

class SnapshotManager:
    """
    Full project snapshot system.

    Captures all tracked files at once, excluding default
    and user-specified patterns.
    """

    def __init__(
        self,
        storage: CheckpointStorage,
        project_root: str | None = None,
        session_id: str = "",
        console: Console | None = None,
    ) -> None:
        self.storage = storage
        self.project_root = project_root or os.getcwd()
        self.session_id = session_id
        self.console = console or Console()

    async def take(
        self,
        description: str = "",
        exclude_patterns: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> Checkpoint:
        """Take a full project snapshot."""
        excludes = list(DEFAULT_EXCLUDES)
        if exclude_patterns:
            excludes.extend(exclude_patterns)

        now = datetime.now(timezone.utc)
        suffix = uuid.uuid4().hex[:4]
        cp_id = f"ckpt_{now.strftime('%Y%m%d_%H%M%S')}_{suffix}"

        files: list[CheckpointFile] = []
        root = Path(self.project_root)

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            rel = path.relative_to(root).as_posix()

            # Check excludes.
            if self._is_excluded(rel, excludes):
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            content_hash = self.storage.store(content)
            files.append(CheckpointFile(
                path=rel,
                content_hash=content_hash,
                size_bytes=len(content.encode("utf-8")),
                encoding="utf-8",
                existed_before=True,
                storage_key=content_hash,
            ))

        checkpoint = Checkpoint(
            id=cp_id,
            timestamp=now,
            session_id=self.session_id,
            tool_name="snapshot",
            description=description or "Full project snapshot",
            files=files,
            metadata={"file_count": len(files)},
            tags=tags or [],
        )

        self.storage.save_checkpoint(checkpoint)

        self.console.print(Panel(
            Text.from_markup(
                f"  ID:      {cp_id}\n"
                f"  Files:   {len(files)} files captured\n"
                f'  Tag:     "{description or "snapshot"}"'
            ),
            title=" 📸 Snapshot Created ",
            title_align="left",
            border_style="green",
            padding=(0, 1),
        ))

        return checkpoint

    async def restore(
        self,
        checkpoint_id: str,
        preview: bool = True,
    ) -> RestoreResult:
        """Restore project to a snapshot."""
        from nexcode.checkpoints.manager import CheckpointManager
        cm = CheckpointManager(
            project_root=self.project_root,
            storage=self.storage,
            session_id=self.session_id,
        )
        return await cm.restore(checkpoint_id, preview=preview)

    def compare(self, checkpoint_a_id: str, checkpoint_b_id: str) -> None:
        """Compare two snapshots."""
        from nexcode.checkpoints.diff import CheckpointDiff
        cp_a = self.storage.load_checkpoint(checkpoint_a_id)
        cp_b = self.storage.load_checkpoint(checkpoint_b_id)
        if not cp_a or not cp_b:
            self.console.print("  [red]Checkpoint not found[/]")
            return
        differ = CheckpointDiff(self.storage, self.project_root, self.console)
        differ.show_between(cp_a, cp_b)

    def _is_excluded(self, rel_path: str, excludes: list[str]) -> bool:
        for pattern in excludes:
            if pattern.endswith("/"):
                if rel_path.startswith(pattern) or f"/{pattern}" in f"/{rel_path}":
                    return True
                dir_name = pattern.rstrip("/")
                parts = rel_path.split("/")
                if dir_name in parts[:-1]:
                    return True
            elif fnmatch.fnmatch(rel_path, pattern):
                return True
            elif fnmatch.fnmatch(os.path.basename(rel_path), pattern):
                return True
        return False


# ---------------------------------------------------------------------------
# TaskUndoManager
# ---------------------------------------------------------------------------

class TaskUndoManager:
    """
    Groups all checkpoints from a single agent task for
    batch undo.
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

    def get_task_checkpoints(self, task_id: str) -> list[Checkpoint]:
        """Get all checkpoints from a specific task."""
        return [
            cp for cp in self.storage.list_checkpoints()
            if cp.task_id == task_id
        ]

    async def undo_task(self, task_id: str, preview: bool = True) -> list[RestoreResult]:
        """Undo everything from a specific task (reverse order)."""
        from nexcode.checkpoints.manager import CheckpointManager

        checkpoints = self.get_task_checkpoints(task_id)
        if not checkpoints:
            return [RestoreResult(error=f"No checkpoints for task {task_id}")]

        if preview:
            self.show_task_changes(task_id)
            try:
                choice = input("  [y] Undo all  [n] Cancel  › ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "n"
            if choice != "y":
                return [RestoreResult(error="Cancelled by user")]

        cm = CheckpointManager(
            project_root=self.project_root,
            storage=self.storage,
        )

        results: list[RestoreResult] = []
        for cp in reversed(checkpoints):  # Restore oldest first.
            r = await cm.restore(cp.id, preview=False)
            results.append(r)

        # Show summary.
        restored = sum(len(r.files_restored) for r in results if r.success)
        deleted = sum(len(r.files_deleted) for r in results if r.success)
        created = sum(len(r.files_created) for r in results if r.success)

        body = Text()
        body.append(f"  Undone {len(checkpoints)} checkpoints\n\n", style="white")
        for r in results:
            if r.success:
                for f in r.files_restored:
                    body.append(f"  ✅ {os.path.basename(f)} → restored\n", style="green")
                for f in r.files_deleted:
                    body.append(f"  ✅ {os.path.basename(f)} → deleted (was created)\n", style="yellow")
                for f in r.files_created:
                    body.append(f"  ✅ {os.path.basename(f)} → recreated\n", style="green")

        self.console.print(Panel(
            body,
            title=" ↩️  Task Undo Complete ",
            title_align="left",
            border_style="green",
            padding=(0, 1),
        ))

        return results

    def show_task_changes(self, task_id: str) -> None:
        """Show summary of what a task changed."""
        checkpoints = self.get_task_checkpoints(task_id)
        if not checkpoints:
            self.console.print("  [dim]No checkpoints for this task[/]")
            return

        all_files: set[str] = set()
        for cp in checkpoints:
            for f in cp.files:
                all_files.add(f.path)

        body = Text()
        body.append(f"  Task: {task_id}\n", style="bold")
        body.append(f"  Checkpoints: {len(checkpoints)}\n", style="dim")
        body.append(f"  Files affected: {len(all_files)}\n\n", style="dim")
        for f in sorted(all_files):
            body.append(f"  📝 {f}\n", style="yellow")

        self.console.print(Panel(
            body,
            title=" Task Changes ",
            title_align="left",
            border_style="yellow",
            padding=(0, 1),
        ))
