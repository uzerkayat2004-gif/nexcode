"""
NexCode Subagent Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Spawns and manages single, parallel, and pipeline subagents.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nexcode.subagents.worker import SubagentConfig, SubagentResult, SubagentWorker


class SubagentManager:
    """
    Spawns and manages multiple subagent workers.

    Supports single, parallel, and pipeline execution.
    """

    def __init__(
        self,
        ai_provider: Any = None,
        tool_registry: Any = None,
        checkpoint_manager: Any = None,
        console: Console | None = None,
    ) -> None:
        self.ai_provider = ai_provider
        self.tool_registry = tool_registry
        self.checkpoint_manager = checkpoint_manager
        self.console = console or Console()
        self._active: dict[str, SubagentWorker] = {}

    # ── Single subagent ────────────────────────────────────────────────────

    async def spawn(
        self,
        instruction: str,
        name: str | None = None,
        allowed_tools: list[str] | None = None,
        context: str | None = None,
        model: str | None = None,
        max_steps: int = 20,
    ) -> SubagentResult:
        """Spawn a single subagent and wait for completion."""
        config = SubagentConfig(
            id=f"sub_{uuid.uuid4().hex[:8]}",
            name=name or f"Subagent-{len(self._active) + 1}",
            instruction=instruction,
            allowed_tools=allowed_tools or [],
            context=context,
            model=model,
            max_steps=max_steps,
        )

        worker = SubagentWorker(
            config=config,
            ai_provider=self.ai_provider,
            tool_registry=self.tool_registry,
            checkpoint_manager=self.checkpoint_manager,
        )
        self._active[config.id] = worker

        result = await worker.run()
        self._active.pop(config.id, None)

        self._show_result(result)
        return result

    # ── Parallel execution ─────────────────────────────────────────────────

    async def spawn_parallel(
        self,
        tasks: list[SubagentConfig],
        max_parallel: int = 5,
    ) -> list[SubagentResult]:
        """Spawn multiple subagents running in parallel."""
        semaphore = asyncio.Semaphore(max_parallel)

        self.console.print(Panel(
            f"  🤖 Spawning {len(tasks)} parallel subagents (max {max_parallel} concurrent)",
            title=" Parallel Execution ",
            border_style="cyan",
        ))

        async def _run_one(config: SubagentConfig) -> SubagentResult:
            async with semaphore:
                worker = SubagentWorker(
                    config=config,
                    ai_provider=self.ai_provider,
                    tool_registry=self.tool_registry,
                    checkpoint_manager=self.checkpoint_manager,
                )
                self._active[config.id] = worker
                result = await worker.run()
                self._active.pop(config.id, None)
                return result

        results = await asyncio.gather(*[_run_one(t) for t in tasks], return_exceptions=True)

        final: list[SubagentResult] = []
        for r in results:
            if isinstance(r, SubagentResult):
                final.append(r)
            elif isinstance(r, Exception):
                final.append(SubagentResult(error=str(r)))

        self._show_summary(final)
        return final

    # ── Pipeline execution ─────────────────────────────────────────────────

    async def spawn_pipeline(
        self,
        tasks: list[SubagentConfig],
    ) -> list[SubagentResult]:
        """Spawn subagents in sequence — output of each feeds the next."""
        results: list[SubagentResult] = []
        previous_output = ""

        for config in tasks:
            if previous_output:
                config.context = (config.context or "") + f"\n\nPrevious step result:\n{previous_output}"

            worker = SubagentWorker(
                config=config,
                ai_provider=self.ai_provider,
                tool_registry=self.tool_registry,
                checkpoint_manager=self.checkpoint_manager,
            )
            self._active[config.id] = worker

            result = await worker.run()
            self._active.pop(config.id, None)
            results.append(result)

            if not result.success:
                break

            previous_output = result.result

        self._show_summary(results)
        return results

    # ── Status and control ─────────────────────────────────────────────────

    def get_all_status(self) -> list[dict[str, Any]]:
        return [w.get_status() for w in self._active.values()]

    async def abort_all(self) -> None:
        if self._active:
            await asyncio.gather(*(worker.abort() for worker in self._active.values()))
        self.console.print("  [yellow]All subagents aborted[/]")

    def summarize_results(self, results: list[SubagentResult]) -> str:
        ok = sum(1 for r in results if r.success)
        failed = len(results) - ok
        total_ms = sum(r.duration_ms for r in results)
        lines = [f"Subagent Results: {ok} succeeded, {failed} failed ({total_ms}ms total)"]
        for r in results:
            icon = "✅" if r.success else "❌"
            lines.append(f"  {icon} {r.name}: {r.result[:100] if r.result else r.error or 'No output'}")
        return "\n".join(lines)

    # ── Display ────────────────────────────────────────────────────────────

    def _show_result(self, result: SubagentResult) -> None:
        icon = "✅" if result.success else "❌"
        body = Text()
        body.append(f"  {icon} {result.name}\n", style="bold")
        body.append(f"  Steps: {result.steps_taken}  Duration: {result.duration_ms}ms\n", style="dim")
        if result.result:
            body.append(f"  {result.result[:200]}\n", style="white")
        if result.error:
            body.append(f"  Error: {result.error}\n", style="red")
        self.console.print(body)

    def _show_summary(self, results: list[SubagentResult]) -> None:
        table = Table(title=" Subagent Results ", border_style="cyan", show_lines=True)
        table.add_column("Name", style="white")
        table.add_column("Status", style="white")
        table.add_column("Steps", style="dim")
        table.add_column("Duration", style="dim")
        table.add_column("Output", style="white", max_width=40)

        for r in results:
            icon = "✅" if r.success else "❌"
            output = (r.result[:40] if r.result else r.error or "—")[:40]
            table.add_row(
                r.name, icon, str(r.steps_taken),
                f"{r.duration_ms}ms", output,
            )

        self.console.print(table)
