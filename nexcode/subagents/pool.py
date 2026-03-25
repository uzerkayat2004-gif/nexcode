"""
NexCode Agent Pool
~~~~~~~~~~~~~~~~~~~~

Pre-warmed pool of subagent workers for faster spawning.
"""

from __future__ import annotations

import asyncio
from typing import Any

from rich.console import Console

from nexcode.subagents.worker import SubagentConfig, SubagentWorker


class AgentPool:
    """
    Pre-warmed pool of subagent workers.

    Maintains a set of ready-to-use workers for faster
    task assignment.  Workers are recycled after use.
    """

    def __init__(
        self,
        size: int = 3,
        ai_provider: Any = None,
        tool_registry: Any = None,
        console: Console | None = None,
    ) -> None:
        self.size = size
        self.ai_provider = ai_provider
        self.tool_registry = tool_registry
        self.console = console or Console()

        self._pool: asyncio.Queue[SubagentWorker] = asyncio.Queue(maxsize=size)
        self._total_created = 0
        self._total_used = 0
        self._initialized = False

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Pre-warm the pool with ready workers."""
        for i in range(self.size):
            worker = self._create_worker(f"pool-worker-{i + 1}")
            self._pool.put_nowait(worker)
        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown all workers in the pool."""
        workers = []
        while not self._pool.empty():
            workers.append(self._pool.get_nowait())

        if workers:
            await asyncio.gather(*(worker.abort() for worker in workers))

        self._initialized = False

    # ── Acquire / Release ──────────────────────────────────────────────────

    async def acquire(self) -> SubagentWorker:
        """Get a ready worker from the pool."""
        if not self._initialized:
            await self.initialize()

        try:
            worker = self._pool.get_nowait()
        except asyncio.QueueEmpty:
            # Pool exhausted — create a new one on the fly.
            self._total_created += 1
            worker = self._create_worker(f"overflow-{self._total_created}")

        self._total_used += 1
        return worker

    async def release(self, worker: SubagentWorker) -> None:
        """Return a worker to the pool (create a fresh one)."""
        fresh = self._create_worker(worker.config.name)
        try:
            self._pool.put_nowait(fresh)
        except asyncio.QueueFull:
            pass  # Pool is full, discard.

    # ── Stats ──────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        return {
            "pool_size": self.size,
            "available": self._pool.qsize(),
            "total_created": self._total_created,
            "total_used": self._total_used,
            "initialized": self._initialized,
        }

    # ── Internal ───────────────────────────────────────────────────────────

    def _create_worker(self, name: str) -> SubagentWorker:
        self._total_created += 1
        return SubagentWorker(
            config=SubagentConfig(name=name),
            ai_provider=self.ai_provider,
            tool_registry=self.tool_registry,
        )
