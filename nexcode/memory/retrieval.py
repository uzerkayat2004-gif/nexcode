"""
NexCode Smart Memory Retrieval
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Automatically injects the most relevant memories into
every AI conversation.  Uses keyword-based relevance
scoring and builds a context string for the system prompt.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from nexcode.memory.long_term import LongTermMemory, Memory
from nexcode.memory.project import ProjectMemoryManager

# ---------------------------------------------------------------------------
# MemoryRetrieval
# ---------------------------------------------------------------------------

class MemoryRetrieval:
    """
    Retrieves the most relevant memories for a given instruction
    and builds a context string for injection into the system prompt.
    """

    def __init__(
        self,
        long_term: LongTermMemory,
        project_manager: ProjectMemoryManager,
    ) -> None:
        self.long_term = long_term
        self.project_manager = project_manager

    # ── Retrieval ──────────────────────────────────────────────────────────

    def get_relevant(
        self,
        instruction: str,
        project_path: str,
        max_memories: int = 10,
    ) -> list[Memory]:
        """
        Get memories most relevant to the current instruction.

        Scores each memory by keyword overlap, category weight,
        project match, recency, and importance.
        """
        project_name = self.project_manager.load_or_create(project_path).project_name

        # Get all candidate memories (project-specific + global).
        candidates: list[Memory] = []
        candidates.extend(self.long_term.list(project=project_name))
        candidates.extend(self.long_term.list(project=None))

        # Deduplicate by ID.
        seen: set[str] = set()
        unique: list[Memory] = []
        for m in candidates:
            if m.id not in seen:
                seen.add(m.id)
                unique.append(m)

        # Score and rank.
        scored = [(m, self.score_relevance(m, instruction)) for m in unique]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Return top N with score > 0.
        return [m for m, s in scored[:max_memories] if s > 0]

    # ── Context building ───────────────────────────────────────────────────

    def build_context(
        self,
        instruction: str,
        project_path: str,
    ) -> str:
        """
        Build a context string of relevant memories for system prompt injection.

        Returns an empty string if no relevant memories found.
        """
        memories = self.get_relevant(instruction, project_path)
        if not memories:
            return ""

        lines = ["=== What I Remember About This Project ==="]
        for m in memories:
            lines.append(f"• {m.content} ({m.category})")
            self.mark_used(m.id)
        lines.append("==========================================")

        return "\n".join(lines)

    # ── Relevance scoring ──────────────────────────────────────────────────

    def score_relevance(self, memory: Memory, instruction: str) -> float:
        """
        Score a memory's relevance to a given instruction.

        Factors:
        - Keyword overlap (0.0 - 0.4)
        - Category weight (0.0 - 0.2)
        - Importance (0.0 - 0.2)
        - Recency (0.0 - 0.1)
        - Use frequency (0.0 - 0.1)
        """
        score = 0.0

        # 1. Keyword overlap.
        instruction_words = set(_tokenize(instruction))
        memory_words = set(_tokenize(memory.content))
        tag_words = set(w.lower() for t in memory.tags for w in t.split())
        memory_words |= tag_words

        if instruction_words and memory_words:
            overlap = len(instruction_words & memory_words)
            score += min(0.4, overlap * 0.1)

        # 2. Category weight — some categories are always relevant.
        always_relevant = {"preference", "code_pattern", "decision"}
        if memory.category in always_relevant:
            score += 0.15
        elif memory.category == "project_fact":
            score += 0.1
        elif memory.category == "error":
            # Errors are relevant if instruction mentions fixing/debugging.
            if any(kw in instruction.lower() for kw in ["fix", "bug", "error", "debug", "fail"]):
                score += 0.2
            else:
                score += 0.05

        # 3. Importance.
        score += memory.importance * 0.2

        # 4. Recency (more recent = more relevant).
        age_days = (datetime.now(UTC) - memory.last_used).total_seconds() / 86400
        recency = max(0, 1 - (age_days / 30))  # decays over 30 days
        score += recency * 0.1

        # 5. Use frequency (used more = more important).
        freq_score = min(1, memory.use_count / 10)
        score += freq_score * 0.1

        return round(score, 3)

    # ── Use tracking ───────────────────────────────────────────────────────

    def mark_used(self, memory_id: str) -> None:
        """Update use stats when a memory is retrieved."""
        self.long_term.mark_used(memory_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple word tokenization for keyword matching."""
    return [w.lower() for w in re.findall(r"[a-zA-Z0-9_]+", text) if len(w) > 2]
