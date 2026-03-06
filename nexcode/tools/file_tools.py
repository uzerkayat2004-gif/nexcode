"""
NexCode File Tools
~~~~~~~~~~~~~~~~~~~

Nine file-system tools for reading, writing, editing, creating,
deleting, listing, moving, copying, and inspecting files.

Every tool extends ``BaseTool`` and returns a ``ToolResult``.
"""

from __future__ import annotations

import mimetypes
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.tree import Tree

from nexcode.tools.base import (
    BaseTool,
    CheckpointManager,
    ToolResult,
    generate_diff_string,
    show_diff,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_MAX_FILE_SIZE = 500 * 1024  # 500 KB
_MAX_LINES_PREVIEW = 1000

_checkpoint: CheckpointManager | None = None


def _get_checkpoint() -> CheckpointManager:
    """Lazy-init a shared CheckpointManager."""
    global _checkpoint
    if _checkpoint is None:
        _checkpoint = CheckpointManager()
    return _checkpoint


def _is_binary(path: Path) -> bool:
    """Heuristic check for binary files."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        # Files with null bytes are likely binary.
        return b"\x00" in chunk
    except OSError:
        return False


def _read_text_safe(path: Path) -> str:
    """Read a text file with encoding fallback."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _resolve_path(path_str: str) -> Path:
    """Resolve a path string relative to cwd."""
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def _gitignore_patterns(root: Path) -> list[str]:
    """Load .gitignore patterns from the project root."""
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        try:
            import pathspec
            text = gitignore.read_text(encoding="utf-8", errors="replace")
            return text.splitlines()
        except ImportError:
            pass
    return []


def _is_ignored(path: Path, root: Path, patterns: list[str]) -> bool:
    """Check if a path matches .gitignore patterns."""
    if not patterns:
        return False
    try:
        import pathspec
        spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
        rel = path.relative_to(root)
        return spec.match_file(str(rel))
    except (ImportError, ValueError):
        return False


def _human_size(size: int) -> str:
    """Format size in bytes as human-readable."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0  # type: ignore[assignment]
    return f"{size:.1f} TB"


# ═══════════════════════════════════════════════════════════════════════════
# 1. ReadFileTool
# ═══════════════════════════════════════════════════════════════════════════

class ReadFileTool(BaseTool):
    """Read a file and return its contents with line numbers."""

    name = "read_file"
    description = (
        "Read the contents of a file. Returns content with line numbers. "
        "Supports optional start_line and end_line for partial reads. "
        "Handles very large files and binary files gracefully."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read.",
            },
            "start_line": {
                "type": "integer",
                "description": "Optional start line (1-indexed).",
            },
            "end_line": {
                "type": "integer",
                "description": "Optional end line (1-indexed, inclusive).",
            },
        },
        "required": ["path"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = _resolve_path(kwargs["path"])
        start_line: int | None = kwargs.get("start_line")
        end_line: int | None = kwargs.get("end_line")

        if not path.is_file():
            return ToolResult.fail(f"File not found: {path}")

        # Binary file detection.
        if _is_binary(path):
            mime = mimetypes.guess_type(str(path))[0] or "unknown"
            size = _human_size(path.stat().st_size)
            return ToolResult.ok(
                output=f"[Binary file: {mime}, {size}]",
                display=f"Binary file: {mime} ({size})",
                file_type=mime,
                size=path.stat().st_size,
            )

        # Large file warning.
        file_size = path.stat().st_size
        content = _read_text_safe(path)
        lines = content.splitlines()
        total_lines = len(lines)

        truncated = False
        if file_size > _MAX_FILE_SIZE and start_line is None and end_line is None:
            lines = lines[:_MAX_LINES_PREVIEW]
            truncated = True

        # Apply line range.
        if start_line is not None or end_line is not None:
            s = (start_line or 1) - 1
            e = end_line or total_lines
            lines = lines[s:e]
            line_offset = s
        else:
            line_offset = 0

        # Format with line numbers.
        numbered: list[str] = []
        width = len(str(line_offset + len(lines)))
        for i, line in enumerate(lines, start=line_offset + 1):
            numbered.append(f"{i:>{width}} │ {line}")

        output = "\n".join(numbered)
        if truncated:
            output += f"\n\n... (truncated — showing {_MAX_LINES_PREVIEW} of {total_lines} lines)"

        return ToolResult.ok(
            output=output,
            display=f"Read {path.name} ({total_lines} lines)",
            total_lines=total_lines,
            truncated=truncated,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2. WriteFileTool
# ═══════════════════════════════════════════════════════════════════════════

class WriteFileTool(BaseTool):
    """Create a new file or completely overwrite an existing file."""

    name = "write_file"
    description = (
        "Create a new file or overwrite an existing file with the given content. "
        "Automatically creates parent directories. Shows a diff preview for "
        "existing files."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write.",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file.",
            },
        },
        "required": ["path", "content"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = _resolve_path(kwargs["path"])
        content: str = kwargs["content"]

        # Auto-create parent directories.
        path.parent.mkdir(parents=True, exist_ok=True)

        # If file exists, checkpoint and generate diff.
        diff_str = ""
        if path.is_file():
            _get_checkpoint().save(str(path))
            old_content = _read_text_safe(path)
            diff_str = generate_diff_string(old_content, content, path.name)

        # Write the file.
        path.write_text(content, encoding="utf-8")

        lines = content.count("\n") + 1
        if diff_str:
            return ToolResult.ok(
                output=f"File written: {path} ({lines} lines)\n\nDiff:\n{diff_str}",
                display=f"Wrote {path.name} ({lines} lines, overwritten)",
                lines=lines,
                overwritten=True,
            )
        else:
            return ToolResult.ok(
                output=f"File created: {path} ({lines} lines)",
                display=f"Created {path.name} ({lines} lines)",
                lines=lines,
                overwritten=False,
            )


# ═══════════════════════════════════════════════════════════════════════════
# 3. EditFileTool ⭐
# ═══════════════════════════════════════════════════════════════════════════

class EditFileTool(BaseTool):
    """Surgically edit a file by replacing a specific string."""

    name = "edit_file"
    description = (
        "Edit a file by finding an exact old_string and replacing it with "
        "new_string. Supports multi-line replacements. Fails if old_string "
        "is not found or matches multiple locations. Creates a checkpoint "
        "before applying."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit.",
            },
            "old_string": {
                "type": "string",
                "description": "Exact string to find in the file.",
            },
            "new_string": {
                "type": "string",
                "description": "String to replace old_string with.",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = _resolve_path(kwargs["path"])
        old_string: str = kwargs["old_string"]
        new_string: str = kwargs["new_string"]

        if not path.is_file():
            return ToolResult.fail(f"File not found: {path}")

        content = _read_text_safe(path)

        # Check for exact match.
        count = content.count(old_string)
        if count == 0:
            return ToolResult.fail(
                f"old_string not found in {path.name}. "
                "Make sure the string matches exactly (including whitespace)."
            )
        if count > 1:
            return ToolResult.fail(
                f"old_string found {count} times in {path.name}. "
                "Please provide a more specific string that matches exactly once."
            )

        # Checkpoint before editing.
        _get_checkpoint().save(str(path))

        # Apply the replacement.
        new_content = content.replace(old_string, new_string, 1)

        # Generate diff for output.
        diff_str = generate_diff_string(content, new_content, path.name)

        # Write the modified file.
        path.write_text(new_content, encoding="utf-8")

        old_lines = old_string.count("\n") + 1
        new_lines = new_string.count("\n") + 1

        return ToolResult.ok(
            output=f"Edited {path.name}: replaced {old_lines} line(s) with {new_lines} line(s)\n\n{diff_str}",
            display=f"Edited {path.name} ({old_lines} → {new_lines} lines)",
            old_lines=old_lines,
            new_lines=new_lines,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. CreateFileTool
# ═══════════════════════════════════════════════════════════════════════════

class CreateFileTool(BaseTool):
    """Create a brand new file (fails if file already exists)."""

    name = "create_file"
    description = (
        "Create a new file with the given content. Fails if the file already "
        "exists — use write_file to overwrite. Automatically creates parent "
        "directories."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the new file.",
            },
            "content": {
                "type": "string",
                "description": "Content for the new file.",
            },
        },
        "required": ["path", "content"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = _resolve_path(kwargs["path"])
        content: str = kwargs["content"]

        if path.exists():
            return ToolResult.fail(
                f"File already exists: {path}. "
                "Use write_file to overwrite, or edit_file to modify."
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        lines = content.count("\n") + 1
        return ToolResult.ok(
            output=f"Created {path} ({lines} lines)",
            display=f"Created {path.name} ({lines} lines)",
            lines=lines,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 5. DeleteFileTool
# ═══════════════════════════════════════════════════════════════════════════

class DeleteFileTool(BaseTool):
    """Delete a file (moves to trash for recovery)."""

    name = "delete_file"
    description = (
        "Delete a file or empty directory. The file is moved to "
        ".nexcode_trash/ for potential recovery, not permanently deleted."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file or empty directory to delete.",
            },
        },
        "required": ["path"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = _resolve_path(kwargs["path"])

        if not path.exists():
            return ToolResult.fail(f"Path not found: {path}")

        # Move to trash instead of permanent delete.
        trash_dir = Path.cwd() / ".nexcode_trash"
        trash_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        trash_name = f"{timestamp}_{path.name}"
        trash_path = trash_dir / trash_name

        try:
            shutil.move(str(path), str(trash_path))
        except OSError as exc:
            return ToolResult.fail(f"Failed to delete: {exc}")

        return ToolResult.ok(
            output=f"Deleted {path} (moved to .nexcode_trash/{trash_name})",
            display=f"Deleted {path.name} (recoverable from .nexcode_trash/)",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 6. ListDirectoryTool
# ═══════════════════════════════════════════════════════════════════════════

class ListDirectoryTool(BaseTool):
    """List files and directories in a Rich tree format."""

    name = "list_directory"
    description = (
        "List files and folders in a directory as a tree structure. "
        "Shows file sizes and respects .gitignore by default. "
        "Supports depth control and toggling hidden/ignored files."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to list. Defaults to current directory.",
            },
            "depth": {
                "type": "integer",
                "description": "Maximum depth to traverse (default: 3).",
            },
            "show_hidden": {
                "type": "boolean",
                "description": "Show hidden files/folders (default: false).",
            },
            "show_ignored": {
                "type": "boolean",
                "description": "Show .gitignore'd files (default: false).",
            },
        },
        "required": [],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = _resolve_path(kwargs.get("path", "."))
        max_depth: int = kwargs.get("depth", 3)
        show_hidden: bool = kwargs.get("show_hidden", False)
        show_ignored: bool = kwargs.get("show_ignored", False)

        if not path.is_dir():
            return ToolResult.fail(f"Directory not found: {path}")

        patterns = _gitignore_patterns(path) if not show_ignored else []

        # Build a flat listing for the AI output.
        entries: list[str] = []
        file_count = 0
        dir_count = 0

        def _walk(current: Path, depth: int, prefix: str = "") -> None:
            nonlocal file_count, dir_count
            if depth > max_depth:
                return

            try:
                children = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return

            for child in children:
                # Skip hidden files.
                if not show_hidden and child.name.startswith("."):
                    continue
                # Skip gitignored files.
                if not show_ignored and _is_ignored(child, path, patterns):
                    continue

                if child.is_dir():
                    dir_count += 1
                    entries.append(f"{prefix}📁 {child.name}/")
                    _walk(child, depth + 1, prefix + "  ")
                else:
                    file_count += 1
                    size = _human_size(child.stat().st_size)
                    entries.append(f"{prefix}📄 {child.name}  ({size})")

        _walk(path, 1)

        output = "\n".join(entries)
        summary = f"{file_count} files, {dir_count} directories"
        output += f"\n\n{summary}"

        return ToolResult.ok(
            output=output,
            display=f"Listed {path.name}/ — {summary}",
            files=file_count,
            directories=dir_count,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 7. MoveFileTool
# ═══════════════════════════════════════════════════════════════════════════

class MoveFileTool(BaseTool):
    """Move or rename a file or directory."""

    name = "move_file"
    description = "Move or rename a file or directory."
    parameters = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Source path to move.",
            },
            "destination": {
                "type": "string",
                "description": "Destination path.",
            },
        },
        "required": ["source", "destination"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        source = _resolve_path(kwargs["source"])
        destination = _resolve_path(kwargs["destination"])

        if not source.exists():
            return ToolResult.fail(f"Source not found: {source}")

        if destination.exists():
            return ToolResult.fail(
                f"Destination already exists: {destination}. "
                "Delete it first or choose a different name."
            )

        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(str(source), str(destination))
        except OSError as exc:
            return ToolResult.fail(f"Move failed: {exc}")

        return ToolResult.ok(
            output=f"Moved {source} → {destination}",
            display=f"Moved {source.name} → {destination.name}",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 8. CopyFileTool
# ═══════════════════════════════════════════════════════════════════════════

class CopyFileTool(BaseTool):
    """Copy a file or directory."""

    name = "copy_file"
    description = "Copy a file or directory to a new location."
    parameters = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Source path to copy.",
            },
            "destination": {
                "type": "string",
                "description": "Destination path.",
            },
        },
        "required": ["source", "destination"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        source = _resolve_path(kwargs["source"])
        destination = _resolve_path(kwargs["destination"])

        if not source.exists():
            return ToolResult.fail(f"Source not found: {source}")

        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            if source.is_dir():
                shutil.copytree(str(source), str(destination))
            else:
                shutil.copy2(str(source), str(destination))
        except OSError as exc:
            return ToolResult.fail(f"Copy failed: {exc}")

        return ToolResult.ok(
            output=f"Copied {source} → {destination}",
            display=f"Copied {source.name} → {destination.name}",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 9. FileInfoTool
# ═══════════════════════════════════════════════════════════════════════════

class FileInfoTool(BaseTool):
    """Return detailed metadata about a file."""

    name = "file_info"
    description = (
        "Get detailed information about a file: size, dates, type, "
        "encoding, line count, and git tracking status."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to inspect.",
            },
        },
        "required": ["path"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = _resolve_path(kwargs["path"])

        if not path.exists():
            return ToolResult.fail(f"Path not found: {path}")

        st = path.stat()
        size = _human_size(st.st_size)
        modified = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        created = datetime.fromtimestamp(st.st_ctime, tz=timezone.utc).isoformat()

        mime = mimetypes.guess_type(str(path))[0] or "unknown"
        is_bin = _is_binary(path) if path.is_file() else False

        info_lines = [
            f"Path:      {path}",
            f"Size:      {size} ({st.st_size:,} bytes)",
            f"Type:      {mime}",
            f"Binary:    {is_bin}",
            f"Modified:  {modified}",
            f"Created:   {created}",
        ]

        # Line count for text files.
        if path.is_file() and not is_bin:
            try:
                content = _read_text_safe(path)
                line_count = content.count("\n") + 1
                info_lines.append(f"Lines:     {line_count:,}")
            except Exception:
                pass

        # Git tracking status.
        try:
            import git
            repo = git.Repo(path.parent, search_parent_directories=True)
            rel = path.relative_to(repo.working_dir)
            tracked = str(rel) not in [i.a_path for i in repo.index.diff(None)]
            untracked = str(rel) in repo.untracked_files
            if untracked:
                info_lines.append("Git:       untracked")
            elif tracked:
                info_lines.append("Git:       tracked")
            else:
                info_lines.append("Git:       modified")
        except Exception:
            info_lines.append("Git:       not in repo")

        output = "\n".join(info_lines)
        return ToolResult.ok(
            output=output,
            display=f"Info: {path.name} ({size})",
        )
