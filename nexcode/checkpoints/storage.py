"""
NexCode Checkpoint Storage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Content-addressable storage engine for checkpoint data.
Uses SHA256 hashing with 2-char prefix sharding for
maximum deduplication and efficient lookups.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexcode.checkpoints.manager import Checkpoint


# ---------------------------------------------------------------------------
# CheckpointStorage
# ---------------------------------------------------------------------------

class CheckpointStorage:
    """
    Content-addressable storage for checkpoint file data.

    Layout::

        base_dir/
        ├── objects/          # file content by SHA256
        │   ├── a3/
        │   │   └── f92c1d...
        │   └── ...
        ├── checkpoints/      # checkpoint metadata JSON
        │   ├── ckpt_..._a3f9.json
        │   └── ...
        └── index.json        # fast lookup index
    """

    def __init__(self, base_dir: str | None = None, project_root: str | None = None) -> None:
        if base_dir:
            self.base = Path(base_dir)
        else:
            project_hash = hashlib.md5(
                (project_root or os.getcwd()).encode()
            ).hexdigest()[:12]
            self.base = Path.home() / ".nexcode" / "checkpoints" / project_hash

        self.objects_dir = self.base / "objects"
        self.checkpoints_dir = self.base / "checkpoints"
        self.index_path = self.base / "index.json"

        # Ensure directories exist.
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    # ── Content storage ────────────────────────────────────────────────────

    def store(self, content: str, encoding: str = "utf-8") -> str:
        """Store file content. Returns SHA256 hash (deduplicates)."""
        content_bytes = content.encode(encoding)
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        if not self.exists(content_hash):
            prefix = content_hash[:2]
            obj_dir = self.objects_dir / prefix
            obj_dir.mkdir(exist_ok=True)
            obj_path = obj_dir / content_hash[2:]
            obj_path.write_bytes(content_bytes)

        return content_hash

    def retrieve(self, content_hash: str) -> str | None:
        """Retrieve file content by hash."""
        prefix = content_hash[:2]
        obj_path = self.objects_dir / prefix / content_hash[2:]
        if not obj_path.exists():
            return None
        try:
            return obj_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return obj_path.read_bytes().decode("utf-8", errors="replace")

    def exists(self, content_hash: str) -> bool:
        """Check if content already stored."""
        prefix = content_hash[:2]
        return (self.objects_dir / prefix / content_hash[2:]).exists()

    # ── Checkpoint metadata ────────────────────────────────────────────────

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint metadata as JSON."""
        path = self.checkpoints_dir / f"{checkpoint.id}.json"
        data = _checkpoint_to_dict(checkpoint)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        self._update_index(checkpoint.id, "add")

    def load_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """Load checkpoint metadata by ID."""
        path = self.checkpoints_dir / f"{checkpoint_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return _dict_to_checkpoint(data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    def list_checkpoints(self) -> list[Checkpoint]:
        """List all checkpoints, newest first."""
        checkpoints: list[Checkpoint] = []
        for f in sorted(self.checkpoints_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                cp = _dict_to_checkpoint(data)
                if cp:
                    checkpoints.append(cp)
            except (json.JSONDecodeError, TypeError):
                continue
        return checkpoints

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete checkpoint metadata. Content GC'd separately."""
        path = self.checkpoints_dir / f"{checkpoint_id}.json"
        if path.exists():
            path.unlink()
            self._update_index(checkpoint_id, "remove")
            return True
        return False

    # ── Storage stats ──────────────────────────────────────────────────────

    def get_size_bytes(self) -> int:
        """Get total storage used."""
        total = 0
        for root, _dirs, files in os.walk(self.base):
            for f in files:
                total += (Path(root) / f).stat().st_size
        return total

    def get_object_count(self) -> int:
        """Count unique stored objects."""
        count = 0
        for d in self.objects_dir.iterdir():
            if d.is_dir():
                count += sum(1 for _ in d.iterdir())
        return count

    def gc(self) -> int:
        """Garbage collect unreferenced content objects. Returns bytes freed."""
        # Collect all referenced hashes.
        referenced: set[str] = set()
        for cp in self.list_checkpoints():
            for f in cp.files:
                referenced.add(f.storage_key)

        # Remove unreferenced objects.
        freed = 0
        for prefix_dir in self.objects_dir.iterdir():
            if not prefix_dir.is_dir():
                continue
            for obj_file in prefix_dir.iterdir():
                full_hash = prefix_dir.name + obj_file.name
                if full_hash not in referenced:
                    freed += obj_file.stat().st_size
                    obj_file.unlink()
            # Remove empty prefix dirs.
            if not any(prefix_dir.iterdir()):
                prefix_dir.rmdir()

        return freed

    # ── Index ──────────────────────────────────────────────────────────────

    def _update_index(self, checkpoint_id: str, action: str) -> None:
        index: list[str] = []
        if self.index_path.exists():
            try:
                index = json.loads(self.index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, TypeError):
                pass
        if action == "add" and checkpoint_id not in index:
            index.insert(0, checkpoint_id)
        elif action == "remove" and checkpoint_id in index:
            index.remove(checkpoint_id)
        self.index_path.write_text(json.dumps(index), encoding="utf-8")


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _checkpoint_to_dict(cp: Checkpoint) -> dict[str, Any]:
    return {
        "id": cp.id,
        "timestamp": cp.timestamp.isoformat(),
        "session_id": cp.session_id,
        "task_id": cp.task_id,
        "tool_name": cp.tool_name,
        "description": cp.description,
        "files": [
            {
                "path": f.path,
                "content_hash": f.content_hash,
                "size_bytes": f.size_bytes,
                "encoding": f.encoding,
                "existed_before": f.existed_before,
                "storage_key": f.storage_key,
            }
            for f in cp.files
        ],
        "metadata": cp.metadata,
        "tags": cp.tags,
    }


def _dict_to_checkpoint(data: dict[str, Any]) -> Checkpoint | None:
    from nexcode.checkpoints.manager import Checkpoint, CheckpointFile
    try:
        files = [
            CheckpointFile(**{k: v for k, v in f.items() if k in CheckpointFile.__dataclass_fields__})
            for f in data.get("files", [])
        ]
        ts = data.get("timestamp", "")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        return Checkpoint(
            id=data["id"],
            timestamp=ts,
            session_id=data.get("session_id", ""),
            task_id=data.get("task_id"),
            tool_name=data.get("tool_name", ""),
            description=data.get("description", ""),
            files=files,
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )
    except (KeyError, TypeError):
        return None
