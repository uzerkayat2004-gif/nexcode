"""
NexCode Long-Term Memory
~~~~~~~~~~~~~~~~~~~~~~~~~

Extracts and stores important facts across sessions.
Supports 8 memory categories, AI-powered extraction,
manual remember/forget, and search.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from rich.console import Console
from rich.table import Table

from nexcode.memory.store import MemoryStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES = [
    "preference",    # user preferences e.g. "prefers tabs over spaces"
    "project_fact",  # project facts e.g. "uses PostgreSQL"
    "code_pattern",  # coding patterns e.g. "always uses dataclasses"
    "credential",    # important paths/names (NOT passwords)
    "decision",      # architectural decisions made
    "error",         # errors and how they were fixed
    "person",        # team members, stakeholders
    "reminder",      # things user explicitly said to remember
]

_MEMORIES_KEY = "memories"

_EXTRACTION_PROMPT = """\
Analyze this conversation and extract important facts worth remembering.
Focus on:
- User preferences (coding style, tools, naming conventions)
- Project facts (stack, architecture, database, APIs used)
- Decisions made (why something was built a certain way)
- Errors fixed (what went wrong and how it was solved)
- Explicit reminders (things user said "remember" about)

Return ONLY a JSON array. Each object:
{{
  "content": "concise fact",
  "category": "preference|project_fact|code_pattern|decision|error|reminder",
  "importance": 0.0-1.0,
  "tags": ["tag1"]
}}

Max 10 memories. Only genuinely useful facts. Skip trivial items.
Conversation:
{conversation}
"""


# ---------------------------------------------------------------------------
# Memory dataclass
# ---------------------------------------------------------------------------

@dataclass
class Memory:
    """A single long-term memory entry."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    content: str = ""
    category: str = "reminder"
    project: str | None = None
    source: str = "manual"       # "auto" or "manual"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used: datetime = field(default_factory=lambda: datetime.now(UTC))
    use_count: int = 0
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["last_used"] = self.last_used.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        data = dict(data)
        for dt_field in ("created_at", "last_used"):
            if isinstance(data.get(dt_field), str):
                data[dt_field] = datetime.fromisoformat(data[dt_field])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# LongTermMemory
# ---------------------------------------------------------------------------

class LongTermMemory:
    """
    Long-term memory engine for NexCode.

    Stores structured facts across sessions, supports AI-powered
    extraction, manual management, and keyword search.
    """

    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()
        self._memories: list[Memory] = []
        self._load()

    # ── AI extraction ──────────────────────────────────────────────────────

    async def extract_from_session(
        self,
        session: Any,
        ai_provider: Any,
    ) -> list[Memory]:
        """
        Auto-extract memories from a completed session using AI.

        Returns the newly created memories.
        """
        messages = getattr(session, "messages", [])
        if not messages:
            return []

        # Build conversation text (last 30 messages, truncated).
        convo_parts: list[str] = []
        for msg in messages[-30:]:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(b.get("text", b.get("content", "")))
                    for b in content if isinstance(b, dict)
                )
            convo_parts.append(f"[{role}]: {str(content)[:300]}")

        conversation_text = "\n".join(convo_parts)
        prompt = _EXTRACTION_PROMPT.format(conversation=conversation_text)

        try:
            response = await ai_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                system="Extract memories as JSON. Return ONLY a JSON array.",
            )
            content = getattr(response, "content", str(response))
            return self._parse_extracted(content, getattr(session, "project_name", None))
        except Exception:
            return []

    # ── Manual management ──────────────────────────────────────────────────

    def remember(
        self,
        content: str,
        category: str = "reminder",
        project: str | None = None,
        importance: float = 0.7,
    ) -> Memory:
        """Manually add a memory."""
        if category not in CATEGORIES:
            category = "reminder"

        mem = Memory(
            content=content,
            category=category,
            project=project,
            source="manual",
            importance=importance,
        )
        self._memories.append(mem)
        self._save()
        return mem

    def forget(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        before = len(self._memories)
        self._memories = [m for m in self._memories if m.id != memory_id]
        if len(self._memories) < before:
            self._save()
            return True
        return False

    def forget_project(self, project: str) -> int:
        """Delete all memories for a project."""
        before = len(self._memories)
        self._memories = [m for m in self._memories if m.project != project]
        deleted = before - len(self._memories)
        if deleted:
            self._save()
        return deleted

    def update(self, memory_id: str, content: str) -> Memory | None:
        """Update an existing memory's content."""
        for mem in self._memories:
            if mem.id == memory_id:
                mem.content = content
                mem.last_used = datetime.now(UTC)
                self._save()
                return mem
        return None

    # ── Querying ───────────────────────────────────────────────────────────

    def list(
        self,
        project: str | None = None,
        category: str | None = None,
    ) -> list[Memory]:
        """List memories, optionally filtered by project or category."""
        results = self._memories
        if project is not None:
            results = [m for m in results if m.project == project]
        if category is not None:
            results = [m for m in results if m.category == category]
        return sorted(results, key=lambda m: m.importance, reverse=True)

    def search(self, query: str) -> list[Memory]:
        """Search memories by keyword."""
        q = query.lower()
        return [
            m for m in self._memories
            if q in m.content.lower() or q in " ".join(m.tags).lower()
        ]

    def get(self, memory_id: str) -> Memory | None:
        for m in self._memories:
            if m.id == memory_id:
                return m
        return None

    # ── Display ────────────────────────────────────────────────────────────

    def show(self, memories: list[Memory] | None = None, console: Console | None = None) -> None:
        """Show memories in a Rich table."""
        console = console or Console()
        mems = memories if memories is not None else self._memories

        if not mems:
            console.print("  [dim]No memories stored.[/dim]")
            return

        table = Table(
            title="🧠 Memories",
            title_style="bold white",
            border_style="bright_black",
            show_lines=True,
        )
        table.add_column("ID", style="dim", width=10)
        table.add_column("Category", min_width=12)
        table.add_column("Content", min_width=30, max_width=50)
        table.add_column("Imp.", width=5)

        cat_colors = {
            "preference": "cyan", "project_fact": "green",
            "code_pattern": "yellow", "decision": "blue",
            "error": "red", "reminder": "magenta",
            "credential": "bright_black", "person": "white",
        }

        for m in mems[:30]:
            color = cat_colors.get(m.category, "white")
            table.add_row(
                m.id,
                f"[{color}]{m.category}[/]",
                m.content[:50],
                f"{m.importance:.1f}",
            )

        console.print()
        console.print(table)
        console.print(f"\n  [dim]{len(mems)} memories total[/]")

    # ── Use tracking ───────────────────────────────────────────────────────

    def mark_used(self, memory_id: str) -> None:
        """Update use stats when a memory is retrieved."""
        for m in self._memories:
            if m.id == memory_id:
                m.use_count += 1
                m.last_used = datetime.now(UTC)
                self._save()
                return

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        data = self.store.load(_MEMORIES_KEY)
        if isinstance(data, list):
            self._memories = []
            for item in data:
                try:
                    self._memories.append(Memory.from_dict(item))
                except (TypeError, KeyError):
                    continue

    def _save(self) -> None:
        self.store.save(_MEMORIES_KEY, [m.to_dict() for m in self._memories])

    # ── Internal ───────────────────────────────────────────────────────────

    def _parse_extracted(self, response: str, project: str | None) -> list[Memory]:
        """Parse AI extraction response into Memory objects."""
        # Find JSON array in response.
        start = response.find("[")
        end = response.rfind("]")
        if start == -1 or end == -1:
            return []

        try:
            items = json.loads(response[start:end + 1])
        except json.JSONDecodeError:
            return []

        new_memories: list[Memory] = []
        for item in items[:10]:
            if not isinstance(item, dict) or "content" not in item:
                continue
            mem = Memory(
                content=item["content"],
                category=item.get("category", "reminder"),
                project=project,
                source="auto",
                importance=float(item.get("importance", 0.5)),
                tags=item.get("tags", []),
            )
            self._memories.append(mem)
            new_memories.append(mem)

        if new_memories:
            self._save()
        return new_memories

    @property
    def count(self) -> int:
        return len(self._memories)

    def __repr__(self) -> str:
        return f"LongTermMemory(count={self.count})"
