"""
NexCode Search Tools
~~~~~~~~~~~~~~~~~~~~~

Four search-and-find tools for navigating and transforming codebases:
  - SearchTextTool   — regex/text search across files
  - FindFilesTool    — find files by name pattern
  - SearchAndReplaceTool — multi-file search & replace
  - ReadManyFilesTool — batch-read multiple files
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any

from nexcode.tools.base import (
    BaseTool,
    ToolResult,
    generate_diff_string,
)
from nexcode.tools.file_tools import (
    _get_checkpoint,
    _gitignore_patterns,
    _human_size,
    _is_binary,
    _is_ignored,
    _read_text_safe,
    _resolve_path,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_MAX_RESULTS = 100
_MAX_READ_MANY_TOTAL = 200_000  # characters (~50K tokens)


# ═══════════════════════════════════════════════════════════════════════════
# 10. SearchTextTool ⭐
# ═══════════════════════════════════════════════════════════════════════════

class SearchTextTool(BaseTool):
    """Search for text or regex patterns across project files."""

    name = "search_text"
    description = (
        "Search for a text pattern or regex across all files in the project. "
        "Returns matching file paths, line numbers, and line content. "
        "Respects .gitignore by default. Supports regex and case sensitivity."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Text or regex pattern to search for.",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory).",
            },
            "file_pattern": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g., '*.py', '*.js').",
            },
            "use_regex": {
                "type": "boolean",
                "description": "Treat pattern as a regex (default: false).",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case-sensitive search (default: true).",
            },
        },
        "required": ["pattern"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        pattern: str = kwargs["pattern"]
        search_path = _resolve_path(kwargs.get("path", "."))
        file_pattern: str | None = kwargs.get("file_pattern")
        use_regex: bool = kwargs.get("use_regex", False)
        case_sensitive: bool = kwargs.get("case_sensitive", True)

        if not search_path.is_dir():
            return ToolResult.fail(f"Directory not found: {search_path}")

        # Compile pattern.
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            if use_regex:
                regex = re.compile(pattern, flags)
            else:
                regex = re.compile(re.escape(pattern), flags)
        except re.error as exc:
            return ToolResult.fail(f"Invalid regex: {exc}")

        gitignore = _gitignore_patterns(search_path)
        matches: list[str] = []
        files_searched = 0
        files_with_matches = 0

        for root, dirs, files in os.walk(search_path):
            root_path = Path(root)

            # Skip hidden and common unneeded directories.
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in ("node_modules", "__pycache__", ".git", "venv", ".venv")
                and not _is_ignored(root_path / d, search_path, gitignore)
            ]

            for filename in files:
                file_path = root_path / filename

                # Skip hidden files.
                if filename.startswith("."):
                    continue

                # Apply file pattern filter.
                if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
                    continue

                # Skip gitignored files.
                if _is_ignored(file_path, search_path, gitignore):
                    continue

                # Skip binary files.
                if await _is_binary(file_path):
                    continue

                files_searched += 1
                try:
                    content = _read_text_safe(file_path)
                except OSError:
                    continue

                file_had_match = False
                for line_num, line in enumerate(content.splitlines(), start=1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(search_path)
                        matches.append(f"{rel_path}:{line_num}: {line.strip()}")
                        file_had_match = True

                        if len(matches) >= _MAX_RESULTS:
                            break

                if file_had_match:
                    files_with_matches += 1

                if len(matches) >= _MAX_RESULTS:
                    break
            if len(matches) >= _MAX_RESULTS:
                break

        if not matches:
            return ToolResult.ok(
                output=f"No matches found for '{pattern}' in {files_searched} files.",
                display=f"No matches for '{pattern}'",
                matches=0,
                files_searched=files_searched,
            )

        output_lines = [f"Found {len(matches)} match(es) in {files_with_matches} file(s):\n"]
        output_lines.extend(matches)

        if len(matches) >= _MAX_RESULTS:
            output_lines.append(f"\n... (results capped at {_MAX_RESULTS})")

        return ToolResult.ok(
            output="\n".join(output_lines),
            display=f"Found {len(matches)} matches in {files_with_matches} files",
            matches=len(matches),
            files_searched=files_searched,
            files_with_matches=files_with_matches,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 11. FindFilesTool
# ═══════════════════════════════════════════════════════════════════════════

class FindFilesTool(BaseTool):
    """Find files by name pattern across the project."""

    name = "find_files"
    description = (
        "Find files by name pattern (glob). Example: '*.py', 'config*', "
        "'test_*.js'. Returns matching file paths with sizes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match file names (e.g., '*.py').",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory).",
            },
        },
        "required": ["pattern"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        pattern: str = kwargs["pattern"]
        search_path = _resolve_path(kwargs.get("path", "."))

        if not search_path.is_dir():
            return ToolResult.fail(f"Directory not found: {search_path}")

        gitignore = _gitignore_patterns(search_path)
        found: list[str] = []

        for root, dirs, files in os.walk(search_path):
            root_path = Path(root)

            # Skip hidden and unneeded directories.
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in ("node_modules", "__pycache__", ".git", "venv", ".venv")
            ]

            for filename in files:
                if fnmatch.fnmatch(filename, pattern):
                    file_path = root_path / filename

                    if _is_ignored(file_path, search_path, gitignore):
                        continue

                    rel = file_path.relative_to(search_path)
                    size = _human_size(file_path.stat().st_size)
                    found.append(f"{rel}  ({size})")

                    if len(found) >= _MAX_RESULTS:
                        break
            if len(found) >= _MAX_RESULTS:
                break

        if not found:
            return ToolResult.ok(
                output=f"No files matching '{pattern}' found.",
                display=f"No files matching '{pattern}'",
                count=0,
            )

        header = f"Found {len(found)} file(s) matching '{pattern}':\n"
        output = header + "\n".join(found)

        if len(found) >= _MAX_RESULTS:
            output += f"\n... (capped at {_MAX_RESULTS})"

        return ToolResult.ok(
            output=output,
            display=f"Found {len(found)} files matching '{pattern}'",
            count=len(found),
        )


# ═══════════════════════════════════════════════════════════════════════════
# 12. SearchAndReplaceTool ⭐
# ═══════════════════════════════════════════════════════════════════════════

class SearchAndReplaceTool(BaseTool):
    """Search and replace across multiple files."""

    name = "search_and_replace"
    description = (
        "Search and replace a text pattern across multiple files. "
        "Shows a full diff preview of all changes. Creates checkpoints "
        "for every modified file. Supports regex and file filtering."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Text or regex pattern to search for.",
            },
            "replacement": {
                "type": "string",
                "description": "Replacement string.",
            },
            "path": {
                "type": "string",
                "description": "Directory to search (default: current directory).",
            },
            "file_pattern": {
                "type": "string",
                "description": "Glob to filter files (e.g., '*.py').",
            },
            "use_regex": {
                "type": "boolean",
                "description": "Treat pattern as regex (default: false).",
            },
        },
        "required": ["pattern", "replacement"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        pattern: str = kwargs["pattern"]
        replacement: str = kwargs["replacement"]
        search_path = _resolve_path(kwargs.get("path", "."))
        file_pattern: str | None = kwargs.get("file_pattern")
        use_regex: bool = kwargs.get("use_regex", False)

        if not search_path.is_dir():
            return ToolResult.fail(f"Directory not found: {search_path}")

        try:
            if use_regex:
                regex = re.compile(pattern)
            else:
                regex = re.compile(re.escape(pattern))
        except re.error as exc:
            return ToolResult.fail(f"Invalid regex: {exc}")

        gitignore = _gitignore_patterns(search_path)
        checkpoint = _get_checkpoint()

        modified_files: list[str] = []
        total_replacements = 0
        all_diffs: list[str] = []

        for root, dirs, files in os.walk(search_path):
            root_path = Path(root)

            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in ("node_modules", "__pycache__", ".git", "venv", ".venv")
            ]

            for filename in files:
                if filename.startswith("."):
                    continue
                if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
                    continue

                file_path = root_path / filename

                if _is_ignored(file_path, search_path, gitignore):
                    continue
                if await _is_binary(file_path):
                    continue

                try:
                    content = _read_text_safe(file_path)
                except OSError:
                    continue

                matches = regex.findall(content)
                if not matches:
                    continue

                # Replace and generate diff.
                new_content = regex.sub(replacement, content)
                rel = file_path.relative_to(search_path)

                diff = generate_diff_string(content, new_content, str(rel))
                if diff:
                    all_diffs.append(diff)

                # Checkpoint and write.
                checkpoint.save(str(file_path))
                file_path.write_text(new_content, encoding="utf-8")

                modified_files.append(str(rel))
                total_replacements += len(matches)

        if not modified_files:
            return ToolResult.ok(
                output=f"No matches for '{pattern}' found.",
                display=f"No matches for '{pattern}'",
                files_modified=0,
                replacements=0,
            )

        output = (
            f"Replaced {total_replacements} occurrence(s) in "
            f"{len(modified_files)} file(s):\n\n"
        )
        output += "\n".join(f"  • {f}" for f in modified_files)
        output += "\n\n" + "\n".join(all_diffs)

        return ToolResult.ok(
            output=output,
            display=f"Replaced {total_replacements} occurrences in {len(modified_files)} files",
            files_modified=len(modified_files),
            replacements=total_replacements,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 13. ReadManyFilesTool
# ═══════════════════════════════════════════════════════════════════════════

class ReadManyFilesTool(BaseTool):
    """Read multiple files at once with smart token budgeting."""

    name = "read_many_files"
    description = (
        "Read multiple files and return all their contents. Uses smart "
        "token budgeting — if the total content is too large, larger files "
        "are truncated to stay within limits."
    )
    parameters = {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths to read.",
            },
        },
        "required": ["paths"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        paths: list[str] = kwargs["paths"]

        if not paths:
            return ToolResult.fail("No file paths provided.")

        results: list[str] = []
        total_chars = 0
        files_read = 0
        files_truncated = 0

        # Calculate per-file budget.
        per_file_budget = _MAX_READ_MANY_TOTAL // max(len(paths), 1)

        for path_str in paths:
            path = _resolve_path(path_str)

            if not path.is_file():
                results.append(f"\n{'═' * 60}\n📄 {path_str}\n{'═' * 60}\n[File not found]")
                continue

            if await _is_binary(path):
                results.append(f"\n{'═' * 60}\n📄 {path_str}\n{'═' * 60}\n[Binary file — skipped]")
                continue

            try:
                content = _read_text_safe(path)
            except OSError as exc:
                results.append(f"\n{'═' * 60}\n📄 {path_str}\n{'═' * 60}\n[Error: {exc}]")
                continue

            # Apply token budget.
            truncated = False
            if len(content) > per_file_budget:
                content = content[:per_file_budget]
                truncated = True
                files_truncated += 1

            total_chars += len(content)
            files_read += 1

            lines = content.splitlines()
            width = len(str(len(lines)))
            numbered = "\n".join(
                f"{i:>{width}} │ {line}" for i, line in enumerate(lines, 1)
            )

            header = f"\n{'═' * 60}\n📄 {path_str} ({len(lines)} lines)\n{'═' * 60}"
            results.append(header + "\n" + numbered)
            if truncated:
                results.append("\n... [truncated to fit token budget]")

            if total_chars >= _MAX_READ_MANY_TOTAL:
                remaining = len(paths) - files_read
                if remaining > 0:
                    results.append(f"\n... [{remaining} file(s) skipped — token budget reached]")
                break

        output = "\n".join(results)
        summary = f"Read {files_read}/{len(paths)} files"
        if files_truncated:
            summary += f" ({files_truncated} truncated)"

        return ToolResult.ok(
            output=output,
            display=summary,
            files_read=files_read,
            files_truncated=files_truncated,
        )
