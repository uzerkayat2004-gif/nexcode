"""
NexCode Checkpoint Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Core orchestrator for saving, restoring, and managing
checkpoints.  Saves file state before every change and
supports atomic restore operations.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

from nexcode.checkpoints.storage import CheckpointStorage


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CheckpointFile:
    """A single file captured in a checkpoint."""

    path: str                  # relative to project root
    content_hash: str          # SHA256 of content
    size_bytes: int = 0
    encoding: str = "utf-8"
    existed_before: bool = True
    storage_key: str = ""      # same as content_hash


@dataclass
class Checkpoint:
    """A saved checkpoint with one or more files."""

    id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = ""
    task_id: str | None = None
    tool_name: str = ""
    description: str = ""
    files: list[CheckpointFile] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class RestoreResult:
    """Result of a restore operation."""

    success: bool = False
    checkpoint: Checkpoint | None = None
    files_restored: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""

    checkpoints_deleted: int = 0
    bytes_freed: int = 0


# ---------------------------------------------------------------------------
# CheckpointManager
# ---------------------------------------------------------------------------

class CheckpointManager:
    """
    Core checkpoint manager.

    Automatically saves file state before modifications and
    supports atomic restore operations (all-or-nothing).
    """

    def __init__(
        self,
        project_root: str | None = None,
        storage: CheckpointStorage | None = None,
        session_id: str = "",
        console: Console | None = None,
    ) -> None:
        self.project_root = project_root or os.getcwd()
        self.storage = storage or CheckpointStorage(project_root=self.project_root)
        self.session_id = session_id
        self.console = console or Console()

    # ── Save ───────────────────────────────────────────────────────────────

    async def save(
        self,
        paths: list[str] | str,
        tool_name: str = "",
        description: str = "",
        task_id: str | None = None,
        tags: list[str] | None = None,
    ) -> Checkpoint:
        """Save checkpoint for one or more files before modification."""
        if isinstance(paths, str):
            paths = [paths]

        now = datetime.now(timezone.utc)
        suffix = uuid.uuid4().hex[:4]
        cp_id = f"ckpt_{now.strftime('%Y%m%d_%H%M%S')}_{suffix}"

        checkpoint_files: list[CheckpointFile] = []

        for path in paths:
            abs_path = self._resolve(path)
            if not os.path.exists(abs_path):
                # File doesn't exist yet — record that.
                checkpoint_files.append(CheckpointFile(
                    path=self._relative(abs_path),
                    content_hash="",
                    size_bytes=0,
                    existed_before=False,
                    storage_key="",
                ))
                continue

            try:
                content = Path(abs_path).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = Path(abs_path).read_bytes().decode("utf-8", errors="replace")
            except OSError as exc:
                self.console.print(f"  [yellow]⚠️  Cannot checkpoint {path}: {exc}[/]")
                continue

            content_hash = self.storage.store(content)
            checkpoint_files.append(CheckpointFile(
                path=self._relative(abs_path),
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
            task_id=task_id,
            tool_name=tool_name,
            description=description or f"Before {tool_name}: {paths[0] if paths else ''}",
            files=checkpoint_files,
            metadata={},
            tags=tags or [],
        )

        self.storage.save_checkpoint(checkpoint)
        return checkpoint

    async def snapshot(
        self,
        description: str = "",
        tags: list[str] | None = None,
    ) -> Checkpoint:
        """Save checkpoint for entire project (delegates to SnapshotManager)."""
        from nexcode.checkpoints.snapshot import SnapshotManager
        sm = SnapshotManager(self.storage, self.project_root, self.session_id)
        return await sm.take(description, tags=tags)

    # ── Restore ────────────────────────────────────────────────────────────

    async def restore(
        self,
        checkpoint_id: str,
        preview: bool = True,
    ) -> RestoreResult:
        """Restore files to a checkpoint state. Atomic — all or nothing."""
        cp = self.get(checkpoint_id)
        if not cp:
            return RestoreResult(error=f"Checkpoint '{checkpoint_id}' not found")

        if preview:
            from nexcode.checkpoints.diff import CheckpointDiff
            differ = CheckpointDiff(self.storage, self.project_root)
            differ.show_restore_preview(cp)
            try:
                choice = input("  [y] Restore  [d] View diff  [n] Cancel  › ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "n"
            if choice == "d":
                differ.show_vs_current(cp)
                try:
                    choice = input("  [y] Restore  [n] Cancel  › ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    choice = "n"
            if choice != "y":
                return RestoreResult(checkpoint=cp, error="Cancelled by user")

        return self._do_restore(cp)

    async def restore_files(
        self,
        checkpoint_id: str,
        paths: list[str],
        preview: bool = True,
    ) -> RestoreResult:
        """Restore only specific files from a checkpoint."""
        cp = self.get(checkpoint_id)
        if not cp:
            return RestoreResult(error=f"Checkpoint '{checkpoint_id}' not found")

        # Filter to requested paths.
        filtered_files = [f for f in cp.files if f.path in paths or self._resolve(f.path) in paths]
        filtered_cp = Checkpoint(
            id=cp.id, timestamp=cp.timestamp, session_id=cp.session_id,
            task_id=cp.task_id, tool_name=cp.tool_name, description=cp.description,
            files=filtered_files, metadata=cp.metadata, tags=cp.tags,
        )
        return self._do_restore(filtered_cp)

    def _do_restore(self, cp: Checkpoint) -> RestoreResult:
        """Perform atomic restore."""
        result = RestoreResult(checkpoint=cp)

        # Phase 1: Gather all content (fail fast if any missing).
        restore_plan: list[tuple[str, str | None, bool]] = []  # (abs_path, content, existed)
        for f in cp.files:
            abs_path = os.path.join(self.project_root, f.path)
            if not f.existed_before:
                # File was created after checkpoint — should be deleted.
                if os.path.exists(abs_path):
                    restore_plan.append((abs_path, None, False))
                continue
            content = self.storage.retrieve(f.storage_key)
            if content is None:
                result.error = f"Missing content for {f.path} (hash: {f.storage_key})"
                return result
            restore_plan.append((abs_path, content, True))

        # Phase 2: Apply all at once.
        for abs_path, content, existed in restore_plan:
            try:
                if content is None:
                    # Delete the file.
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        result.files_deleted.append(abs_path)
                elif not os.path.exists(abs_path):
                    # Recreate deleted file.
                    Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(abs_path).write_text(content, encoding="utf-8")
                    result.files_created.append(abs_path)
                else:
                    # Overwrite with checkpoint content.
                    Path(abs_path).write_text(content, encoding="utf-8")
                    result.files_restored.append(abs_path)
            except OSError as exc:
                result.error = f"Failed to restore {abs_path}: {exc}"
                return result

        result.success = True
        return result

    # ── Undo ───────────────────────────────────────────────────────────────

    async def undo(self) -> RestoreResult:
        """Undo the most recent checkpoint."""
        checkpoints = self.list(limit=1)
        if not checkpoints:
            return RestoreResult(error="No checkpoints to undo")
        return await self.restore(checkpoints[0].id, preview=False)

    async def undo_steps(self, steps: int) -> list[RestoreResult]:
        """Undo last N checkpoints sequentially."""
        checkpoints = self.list(limit=steps)
        results: list[RestoreResult] = []
        for cp in checkpoints:
            r = await self.restore(cp.id, preview=False)
            results.append(r)
            if not r.success:
                break
        return results

    # ── Query ──────────────────────────────────────────────────────────────

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        return self.storage.load_checkpoint(checkpoint_id)

    def get_session_checkpoints(self) -> list[Checkpoint]:
        return [cp for cp in self.storage.list_checkpoints() if cp.session_id == self.session_id]

    def get_file_checkpoints(self, path: str) -> list[Checkpoint]:
        rel = self._relative(path)
        return [cp for cp in self.storage.list_checkpoints() if any(f.path == rel for f in cp.files)]

    def list(
        self,
        session_id: str | None = None,
        path: str | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> list[Checkpoint]:
        all_cps = self.storage.list_checkpoints()
        filtered = all_cps
        if session_id:
            filtered = [cp for cp in filtered if cp.session_id == session_id]
        if path:
            rel = self._relative(path)
            filtered = [cp for cp in filtered if any(f.path == rel for f in cp.files)]
        if tag:
            filtered = [cp for cp in filtered if tag in cp.tags]
        return filtered[:limit]

    # ── Tag / Delete / Cleanup ─────────────────────────────────────────────

    def tag(self, checkpoint_id: str, tag_name: str) -> bool:
        cp = self.get(checkpoint_id)
        if not cp:
            return False
        if tag_name not in cp.tags:
            cp.tags.append(tag_name)
        self.storage.save_checkpoint(cp)
        return True

    def delete(self, checkpoint_id: str) -> bool:
        return self.storage.delete_checkpoint(checkpoint_id)

    def cleanup(
        self,
        max_per_file: int = 50,
        max_age_days: int = 30,
        keep_tagged: bool = True,
        keep_snapshots: bool = True,
    ) -> CleanupResult:
        """Clean up old checkpoints. Returns stats."""
        result = CleanupResult()
        all_cps = self.storage.list_checkpoints()
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 86400)

        to_delete: list[str] = []
        for cp in all_cps:
            if keep_tagged and cp.tags:
                continue
            if keep_snapshots and cp.tool_name == "snapshot":
                continue
            if cp.timestamp.timestamp() < cutoff:
                to_delete.append(cp.id)

        for cp_id in to_delete:
            if self.storage.delete_checkpoint(cp_id):
                result.checkpoints_deleted += 1

        result.bytes_freed = self.storage.gc()
        return result

    def get_storage_size(self) -> int:
        return self.storage.get_size_bytes()

    # ── Helpers ────────────────────────────────────────────────────────────

    def _resolve(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.join(self.project_root, path)

    def _relative(self, path: str) -> str:
        try:
            return os.path.relpath(path, self.project_root).replace("\\", "/")
        except ValueError:
            return path.replace("\\", "/")
