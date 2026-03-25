"""
NexCode Task Coordinator
~~~~~~~~~~~~~~~~~~~~~~~~~~~

AI-powered task decomposition and parallel execution.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nexcode.subagents.manager import SubagentManager
from nexcode.subagents.worker import SubagentConfig, SubagentResult


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CoordinatorResult:
    """Result of a coordinated parallel execution."""

    instruction: str = ""
    parallelized: bool = False
    subtask_count: int = 0
    results: list[SubagentResult] = field(default_factory=list)
    combined_summary: str = ""
    total_duration_ms: int = 0
    speedup_factor: float = 1.0
    total_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# TaskCoordinator
# ---------------------------------------------------------------------------

class TaskCoordinator:
    """
    Intelligently breaks complex tasks into parallel subtasks.

    Uses AI to decide if parallelization is beneficial and
    to decompose the instruction into independent chunks.
    """

    def __init__(
        self,
        ai_provider: Any = None,
        subagent_manager: SubagentManager | None = None,
        console: Console | None = None,
    ) -> None:
        self.ai_provider = ai_provider
        self.manager = subagent_manager
        self.console = console or Console()

    # ── Detect parallelizability ───────────────────────────────────────────

    async def can_parallelize(self, instruction: str) -> bool:
        """Use AI to decide if a task can be parallelized."""
        keywords = [
            "all files", "all modules", "each file", "every file",
            "all python", "all tests", "add to all", "update all",
            "all classes", "all functions", "each module",
        ]
        lower = instruction.lower()

        # Quick heuristic check.
        if any(kw in lower for kw in keywords):
            return True

        # AI check.
        if self.ai_provider:
            try:
                prompt = (
                    f"Can this task be split into parallel subtasks? Answer YES or NO.\n"
                    f"Task: {instruction}"
                )
                resp = await self.ai_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system="Answer only YES or NO.",
                )
                text = getattr(resp, "content", str(resp)).strip().upper()
                return text.startswith("YES")
            except Exception:
                pass

        return False

    # ── Decompose ──────────────────────────────────────────────────────────

    async def decompose(
        self,
        instruction: str,
        context: str = "",
    ) -> list[SubagentConfig]:
        """Break a complex task into parallel subtask configurations."""
        if not self.ai_provider:
            # Can't decompose without AI — return single task.
            return [SubagentConfig(
                id=f"sub_{uuid.uuid4().hex[:8]}",
                name="Main Task",
                instruction=instruction,
            )]

        try:
            prompt = (
                f"Break this task into independent subtasks that can run in parallel.\n"
                f"Task: {instruction}\n\n"
                f"Context:\n{context[:2000]}\n\n"
                f"Return each subtask as one line: NAME: instruction\n"
                f"Only return lines in the format above."
            )
            resp = await self.ai_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You decompose tasks into parallel subtasks. Return only NAME: instruction lines.",
            )
            text = getattr(resp, "content", str(resp))

            configs: list[SubagentConfig] = []
            for line in text.strip().splitlines():
                line = line.strip()
                if ":" not in line:
                    continue
                parts = line.split(":", 1)
                name = parts[0].strip().strip("-").strip("0123456789.").strip()
                instr = parts[1].strip()
                if name and instr:
                    configs.append(SubagentConfig(
                        id=f"sub_{uuid.uuid4().hex[:8]}",
                        name=name[:30],
                        instruction=instr,
                        context=context,
                        max_steps=20,
                    ))

            return configs if configs else [SubagentConfig(
                id=f"sub_{uuid.uuid4().hex[:8]}",
                name="Main Task",
                instruction=instruction,
            )]

        except Exception:
            return [SubagentConfig(
                id=f"sub_{uuid.uuid4().hex[:8]}",
                name="Main Task",
                instruction=instruction,
            )]

    # ── Smart run ──────────────────────────────────────────────────────────

    async def run_smart(
        self,
        instruction: str,
        context: Any = None,
    ) -> CoordinatorResult:
        """Run a task using parallelization if possible."""
        can_par = await self.can_parallelize(instruction)

        if not can_par or not self.manager:
            # Run as single task.
            if self.manager:
                result = await self.manager.spawn(SubagentConfig(instruction=instruction))
                return CoordinatorResult(
                    instruction=instruction,
                    parallelized=False,
                    subtask_count=1,
                    results=[result],
                    combined_summary=result.result,
                    total_duration_ms=result.duration_ms,
                )
            return CoordinatorResult(instruction=instruction, combined_summary="No manager available")

        # Decompose and run in parallel.
        ctx_str = ""
        if context and hasattr(context, "to_string"):
            ctx_str = context.to_string()

        tasks = await self.decompose(instruction, ctx_str)

        approved = await self.preview_decomposition(tasks)
        if not approved:
            return CoordinatorResult(instruction=instruction, combined_summary="Cancelled by user")

        results = await self.manager.spawn_parallel(tasks)

        total_ms = sum(r.duration_ms for r in results)
        max_ms = max((r.duration_ms for r in results), default=1)
        speedup = total_ms / max(max_ms, 1)
        total_cost = sum(r.cost_usd for r in results)

        combined = self.manager.summarize_results(results)

        return CoordinatorResult(
            instruction=instruction,
            parallelized=True,
            subtask_count=len(tasks),
            results=results,
            combined_summary=combined,
            total_duration_ms=max_ms,
            speedup_factor=speedup,
            total_cost_usd=total_cost,
        )

    # ── Preview ────────────────────────────────────────────────────────────

    async def preview_decomposition(self, tasks: list[SubagentConfig]) -> bool:
        """Show decomposition plan and ask user for approval."""
        body = Text()
        body.append(f"\n  Decomposed into {len(tasks)} parallel subagents:\n\n", style="bold")

        for i, t in enumerate(tasks, 1):
            body.append(f"  {i}. ", style="cyan")
            body.append(f"{t.name}: ", style="bold white")
            body.append(f"{t.instruction[:80]}\n", style="dim")

        body.append(f"\n  Expected speedup: ~{len(tasks)}x faster than sequential\n", style="green")

        self.console.print(Panel(body, title=" Parallel Plan ", border_style="cyan", padding=(0, 1)))

        try:
            choice = input("  [y] Run parallel  [s] Run sequential  [n] Cancel  › ").strip().lower()
            return choice in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False
