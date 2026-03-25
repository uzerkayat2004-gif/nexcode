"""
NexCode Memory Store
~~~~~~~~~~~~~~~~~~~~~

Simple, fast JSON-file storage backend for all memory data.
Provides save/load/delete/search operations and backup/restore.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_BASE = Path.home() / ".nexcode" / "memory"


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

class MemoryStore:
    """
    JSON-file storage backend for NexCode memory.

    Each key maps to a JSON file on disk.  Provides CRUD
    operations, prefix-based listing, full-text search,
    and backup / restore.
    """

    def __init__(self, base_path: str | Path | None = None) -> None:
        self.base = Path(base_path) if base_path else _DEFAULT_BASE
        self.base.mkdir(parents=True, exist_ok=True)

    # ── CRUD ───────────────────────────────────────────────────────────────

    def save(self, key: str, data: dict[str, Any] | list[Any]) -> None:
        """Save data under a key (creates parent dirs as needed)."""
        path = self._key_to_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(
                json.dumps(data, default=str, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise MemoryStoreError(f"Failed to save '{key}': {exc}") from exc

    def load(self, key: str) -> dict[str, Any] | list[Any] | None:
        """Load data by key.  Returns None if not found or corrupt."""
        path = self._key_to_path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def delete(self, key: str) -> bool:
        """Delete data by key."""
        path = self._key_to_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        return self._key_to_path(key).exists()

    # ── Listing & search ───────────────────────────────────────────────────

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys matching a prefix."""
        search_dir = self.base / prefix.replace("/", os.sep) if prefix else self.base
        if not search_dir.exists():
            return []

        keys: list[str] = []
        for path in search_dir.rglob("*.json"):
            rel = path.relative_to(self.base).with_suffix("")
            keys.append(str(rel).replace(os.sep, "/"))
        return sorted(keys)

    def search(self, query: str, prefix: str = "") -> list[dict[str, Any]]:
        """Full-text search across stored data matching a prefix."""
        query_lower = query.lower()
        results: list[dict[str, Any]] = []

        for key in self.list_keys(prefix):
            data = self.load(key)
            if data is None:
                continue

            text = json.dumps(data, default=str).lower()
            if query_lower in text:
                results.append({"key": key, "data": data})
                if len(results) >= 50:
                    break

        return results

    # ── Storage info ───────────────────────────────────────────────────────

    def get_size(self) -> int:
        """Total storage size in bytes."""
        total = 0
        for path in self.base.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total

    def get_size_display(self) -> str:
        """Human-readable storage size."""
        size = self.get_size()
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    # ── Backup / restore ──────────────────────────────────────────────────

    def export_backup(self, output_path: str) -> None:
        """Export all data as a single JSON backup file."""
        backup: dict[str, Any] = {
            "exported_at": datetime.now(UTC).isoformat(),
            "data": {},
        }

        for key in self.list_keys():
            data = self.load(key)
            if data is not None:
                backup["data"][key] = data

        Path(output_path).write_text(
            json.dumps(backup, default=str, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def import_backup(self, backup_path: str) -> int:
        """Import from a backup file.  Returns count of keys restored."""
        try:
            backup = json.loads(Path(backup_path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise MemoryStoreError(f"Invalid backup: {exc}") from exc

        data = backup.get("data", {})
        count = 0
        for key, value in data.items():
            self.save(key, value)
            count += 1
        return count

    def clear_all(self) -> None:
        """Delete all stored data.  Use with caution."""
        if self.base.exists():
            shutil.rmtree(self.base)
            self.base.mkdir(parents=True, exist_ok=True)

    # ── Internal ───────────────────────────────────────────────────────────

    def _key_to_path(self, key: str) -> Path:
        """Convert a key like 'projects/abc123' to a file path."""
        safe_key = key.replace("/", os.sep)
        path = self.base / f"{safe_key}.json"
        return path

    def __repr__(self) -> str:
        return f"MemoryStore(base={self.base}, size={self.get_size_display()})"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class MemoryStoreError(Exception):
    """A memory store operation failed."""
    pass
