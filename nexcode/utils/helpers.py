"""
NexCode Shared Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~

Common helper functions used across the NexCode codebase.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path


def timestamp_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def timestamp_short() -> str:
    """Return a compact human-readable timestamp (e.g., '2024-01-15 14:30')."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def slugify(text: str, *, max_length: int = 64) -> str:
    """
    Convert arbitrary text to a filesystem-safe slug.

    Args:
        text: The input text.
        max_length: Maximum slug length.

    Returns:
        A lowercase, hyphen-separated slug string.
    """
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_length]


def truncate(text: str, max_length: int = 80, *, suffix: str = "…") -> str:
    """
    Truncate text to *max_length* characters, appending *suffix* if truncated.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def file_size_human(size_bytes: int) -> str:
    """Convert a file size in bytes to a human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0  # type: ignore[assignment]
    return f"{size_bytes:.1f} PB"


def resolve_path(path_str: str, base: Path | None = None) -> Path:
    """
    Resolve a path string to an absolute ``Path``.

    Handles ``~`` expansion and makes relative paths absolute
    relative to *base* (defaults to cwd).
    """
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = (base or Path.cwd()) / p
    return p.resolve()


class Timer:
    """
    Simple context-manager timer for profiling code blocks.

    Usage::

        with Timer() as t:
            do_work()
        print(f"Took {t.elapsed:.2f}s")
    """

    def __init__(self) -> None:
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    @property
    def elapsed(self) -> float:
        """Elapsed time in seconds."""
        return self.end_time - self.start_time

    def __enter__(self) -> Timer:
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self.end_time = time.perf_counter()
