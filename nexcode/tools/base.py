"""
NexCode Base Tool System
~~~~~~~~~~~~~~~~~~~~~~~~~

Foundation classes for the NexCode tool system:
  - ``ToolResult`` — standardized tool output
  - ``BaseTool`` — abstract base class all tools extend
  - ``PermissionManager`` — ask/auto/strict permission enforcement
  - ``CheckpointManager`` — auto-backup before file modifications
  - ``show_diff()`` — colored Rich diff display
"""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# ---------------------------------------------------------------------------
# ToolResult — standardized output from every tool
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """
    Standardized result returned by every tool execution.

    Attributes:
        success: Whether the operation completed without errors.
        output: Content returned to the AI (machine-readable).
        display: Content shown to the user in the terminal (human-friendly).
        error: Error message if the operation failed.
        metadata: Arbitrary extra data (e.g., line count, file size).
    """

    success: bool
    output: str
    display: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, output: str, display: str = "", **metadata: Any) -> ToolResult:
        """Shorthand for a successful result."""
        return cls(success=True, output=output, display=display or output, metadata=metadata)

    @classmethod
    def fail(cls, error: str, display: str = "") -> ToolResult:
        """Shorthand for a failed result."""
        return cls(success=False, output="", display=display or error, error=error)


# ---------------------------------------------------------------------------
# BaseTool — abstract base class
# ---------------------------------------------------------------------------

class BaseTool(ABC):
    """
    Abstract base class that every NexCode tool must extend.

    Each tool defines its name, description, parameter schema, and
    an ``execute()`` method.  The registry uses ``to_api_schema()``
    to generate the tool definitions sent to the AI provider.
    """

    # Subclasses must define these.
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    # Whether this tool modifies files (used by PermissionManager).
    is_destructive: bool = False

    # Whether this tool is read-only (skip permission checks in "ask" mode).
    is_read_only: bool = False

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given parameters."""
        ...

    def to_api_schema(self) -> dict[str, Any]:
        """
        Convert to the tool format expected by LLM APIs
        (OpenAI / Anthropic function-calling schema).
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


# ---------------------------------------------------------------------------
# PermissionManager — enforces ask / auto / strict modes
# ---------------------------------------------------------------------------

class PermissionManager:
    """
    Controls whether tool calls require user confirmation.

    Modes:
        - ``ask``:    Confirm before write/delete/move operations.
                      Read operations execute freely.
        - ``auto``:   Execute everything without asking.
        - ``strict``: Confirm before *every* operation, including reads.
    """

    def __init__(self, mode: str = "ask", console: Console | None = None) -> None:
        self.mode = mode
        self.console = console or Console()
        # Tools the user has permanently allowed this session.
        self._always_allowed: set[str] = set()

    def requires_permission(self, tool: BaseTool) -> bool:
        """Check whether a tool call needs user confirmation."""
        if tool.name in self._always_allowed:
            return False

        if self.mode == "auto":
            return False
        elif self.mode == "strict":
            return True
        else:  # "ask"
            return not tool.is_read_only

    def request_permission(
        self,
        tool: BaseTool,
        *,
        action_summary: str = "",
        target: str = "",
    ) -> bool:
        """
        Show a permission panel and wait for user input.

        Returns True if the user grants permission.
        """
        if not self.requires_permission(tool):
            return True

        # Build the permission panel.
        body = Text()
        body.append("Tool:    ", style="dim")
        body.append(f"{tool.name}\n", style="bold white")

        if target:
            body.append("File:    ", style="dim")
            body.append(f"{target}\n", style="bold white")

        if action_summary:
            body.append("Action:  ", style="dim")
            body.append(f"{action_summary}\n", style="bold white")

        body.append("\n")
        body.append("[y]", style="bold green")
        body.append(" Yes   ", style="dim")
        body.append("[n]", style="bold red")
        body.append(" No   ", style="dim")
        body.append("[a]", style="bold cyan")
        body.append(" Always allow", style="dim")

        self.console.print(
            Panel(
                body,
                title="[bold yellow]🔧 Tool Request[/]",
                title_align="left",
                border_style="yellow",
                padding=(1, 2),
            )
        )

        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False

        if choice in ("y", "yes"):
            return True
        elif choice in ("a", "always"):
            self._always_allowed.add(tool.name)
            return True
        else:
            return False

    def always_allow(self, tool_name: str) -> None:
        """Mark a tool as permanently allowed for this session."""
        self._always_allowed.add(tool_name)


# ---------------------------------------------------------------------------
# CheckpointManager — auto-backup before file modifications
# ---------------------------------------------------------------------------

@dataclass
class Checkpoint:
    """Metadata for a single file checkpoint."""

    checkpoint_id: str
    file_path: str
    timestamp: str
    size_bytes: int
    backup_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "file_path": self.file_path,
            "timestamp": self.timestamp,
            "size_bytes": self.size_bytes,
            "backup_path": self.backup_path,
        }


class CheckpointManager:
    """
    Auto-backup system that saves file state before modifications.

    Checkpoints are stored at ``~/.nexcode/checkpoints/<project_hash>/``
    and can be restored via the ``/rewind`` slash command.
    """

    MAX_CHECKPOINTS_PER_FILE: int = 20

    def __init__(self, workspace_root: Path | None = None) -> None:
        self.workspace_root = workspace_root or Path.cwd()
        project_hash = hashlib.md5(
            str(self.workspace_root.resolve()).encode()
        ).hexdigest()[:12]
        self.storage_dir = Path.home() / ".nexcode" / "checkpoints" / project_hash
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.storage_dir / "index.json"
        self._index: list[dict[str, Any]] = self._load_index()

    def save(self, path: str) -> str:
        """
        Save the current state of a file as a checkpoint.

        Args:
            path: Path to the file to checkpoint.

        Returns:
            The checkpoint ID (used for restore).
        """
        file_path = Path(path).resolve()
        if not file_path.is_file():
            return ""

        # Generate a unique checkpoint ID.
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
        checkpoint_id = f"{ts}_{file_hash}"

        # Copy the file to the checkpoint directory.
        backup_path = self.storage_dir / f"{checkpoint_id}_{file_path.name}"
        shutil.copy2(str(file_path), str(backup_path))

        # Record in the index.
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            file_path=str(file_path),
            timestamp=datetime.now(UTC).isoformat(),
            size_bytes=file_path.stat().st_size,
            backup_path=str(backup_path),
        )
        self._index.append(checkpoint.to_dict())
        self._save_index()

        # Enforce per-file limit.
        self._cleanup_file(str(file_path))

        return checkpoint_id

    def restore(self, checkpoint_id: str) -> bool:
        """
        Restore a file to a previous checkpoint.

        Returns True on success.
        """
        for entry in self._index:
            if entry["checkpoint_id"] == checkpoint_id:
                backup = Path(entry["backup_path"])
                target = Path(entry["file_path"])
                if backup.is_file():
                    shutil.copy2(str(backup), str(target))
                    return True
                return False
        return False

    def list(self, path: str | None = None) -> list[Checkpoint]:
        """
        List all checkpoints, optionally filtered by file path.
        """
        results: list[Checkpoint] = []
        for entry in self._index:
            if path is None or Path(entry["file_path"]).resolve() == Path(path).resolve():
                results.append(Checkpoint(**entry))
        results.sort(key=lambda c: c.timestamp, reverse=True)
        return results

    def cleanup(self) -> int:
        """
        Remove old checkpoints exceeding the per-file limit.

        Returns the number of checkpoints removed.
        """
        removed = 0
        # Group by file path.
        by_file: dict[str, list[dict[str, Any]]] = {}
        for entry in self._index:
            by_file.setdefault(entry["file_path"], []).append(entry)

        for file_path, entries in by_file.items():
            removed += self._cleanup_file(file_path)

        return removed

    def _cleanup_file(self, file_path: str) -> int:
        """Remove excess checkpoints for a single file."""
        entries = [e for e in self._index if e["file_path"] == file_path]
        entries.sort(key=lambda e: e["timestamp"])

        removed = 0
        while len(entries) > self.MAX_CHECKPOINTS_PER_FILE:
            oldest = entries.pop(0)
            backup = Path(oldest["backup_path"])
            if backup.is_file():
                backup.unlink()
            self._index = [e for e in self._index if e["checkpoint_id"] != oldest["checkpoint_id"]]
            removed += 1

        if removed:
            self._save_index()
        return removed

    def _load_index(self) -> list[dict[str, Any]]:
        """Load the checkpoint index from disk."""
        if self._index_path.is_file():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                pass
        return []

    def _save_index(self) -> None:
        """Persist the checkpoint index to disk."""
        self._index_path.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def __repr__(self) -> str:
        return f"CheckpointManager(dir={self.storage_dir}, checkpoints={len(self._index)})"


# ---------------------------------------------------------------------------
# Diff display — colored Rich output for file changes
# ---------------------------------------------------------------------------

def show_diff(
    old_content: str,
    new_content: str,
    file_path: str = "",
    console: Console | None = None,
    context_lines: int = 3,
) -> str:
    """
    Display a colored diff between old and new content.

    Uses Rich markup:
      - Removed lines → red with ``-`` prefix
      - Added lines   → green with ``+`` prefix
      - Context lines  → dim gray

    Args:
        old_content: The original file content.
        new_content: The modified file content.
        file_path: File name for the panel title.
        console: Rich console to print to.
        context_lines: Number of unchanged context lines around changes.

    Returns:
        The unified diff as a plain string.
    """
    console = console or Console()

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{file_path}" if file_path else "before",
        tofile=f"b/{file_path}" if file_path else "after",
        n=context_lines,
    )

    diff_text = Text()
    plain_lines: list[str] = []

    for line in diff:
        plain_lines.append(line)
        stripped = line.rstrip("\n")

        if line.startswith("+++") or line.startswith("---"):
            diff_text.append(stripped + "\n", style="bold white")
        elif line.startswith("@@"):
            diff_text.append(stripped + "\n", style="cyan")
        elif line.startswith("+"):
            diff_text.append(stripped + "\n", style="green")
        elif line.startswith("-"):
            diff_text.append(stripped + "\n", style="red")
        else:
            diff_text.append(stripped + "\n", style="bright_black")

    if not plain_lines:
        console.print("  [dim]No changes.[/dim]")
        return ""

    title = f" {file_path} " if file_path else " Diff "
    console.print(
        Panel(
            diff_text,
            title=title,
            title_align="center",
            border_style="bright_black",
            padding=(0, 1),
        )
    )

    return "".join(plain_lines)


def generate_diff_string(old_content: str, new_content: str, file_path: str = "") -> str:
    """
    Generate a unified diff string without printing.

    Useful for including diffs in tool output for the AI.
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{file_path}" if file_path else "before",
        tofile=f"b/{file_path}" if file_path else "after",
        n=3,
    )
    return "".join(diff)
