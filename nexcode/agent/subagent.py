"""
NexCode Subagent Manager
~~~~~~~~~~~~~~~~~~~~~~~~~

Spawns isolated sub-loops for parallel subtask execution.
Each subagent gets its own context and limited tool set.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SubagentTask:
    """Definition of a subtask for a subagent."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    instruction: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    context: str | None = None


@dataclass
class SubagentResult:
    """Result of a completed subagent execution."""

    task_id: str
    success: bool
    result: str
    steps_taken: int = 0
    files_modified: list[str] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# SubagentManager
# ---------------------------------------------------------------------------

class SubagentManager:
    """
    Manages spawning and tracking of subagent loops.

    Each subagent runs in its own isolated context with a
    restricted tool set, allowing parallel execution of
    independent subtasks.
    """

    def __init__(
        self,
        ai_provider: Any,
        tool_registry: Any,
        console: Console | None = None,
    ) -> None:
        self.ai_provider = ai_provider
        self.tool_registry = tool_registry
        self.console = console or Console()
        self._active: dict[str, dict[str, Any]] = {}
        self._results: dict[str, SubagentResult] = {}

    # ── Spawn single subagent ──────────────────────────────────────────────

    async def spawn(
        self,
        task: str,
        tools: list[str] | None = None,
        context: str | None = None,
    ) -> SubagentResult:
        """
        Spawn a single subagent for a subtask.

        Args:
            task: The instruction for the subagent.
            tools: Allowed tool names (None = all tools).
            context: Additional context to provide.

        Returns:
            The result of the subagent's work.
        """
        task_id = uuid.uuid4().hex[:8]
        self._active[task_id] = {
            "task": task[:60],
            "status": "🔄 Running",
            "steps": 0,
        }

        try:
            result = await self._run_subagent(task_id, task, tools, context)
            self._active[task_id]["status"] = "✅ Done"
            self._results[task_id] = result
            return result
        except Exception as exc:
            self._active[task_id]["status"] = "❌ Failed"
            result = SubagentResult(
                task_id=task_id,
                success=False,
                result="",
                error=str(exc),
            )
            self._results[task_id] = result
            return result
        finally:
            # Keep in active for status display, clean up later.
            pass

    # ── Spawn parallel subagents ───────────────────────────────────────────

    async def spawn_parallel(
        self,
        tasks: list[SubagentTask],
    ) -> list[SubagentResult]:
        """
        Spawn multiple subagents in parallel.

        All tasks run concurrently via asyncio.gather.
        """
        coroutines = [
            self.spawn(
                task=t.instruction,
                tools=t.allowed_tools or None,
                context=t.context,
            )
            for t in tasks
        ]

        results = await asyncio.gather(*coroutines, return_exceptions=True)

        final: list[SubagentResult] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final.append(SubagentResult(
                    task_id=tasks[i].id,
                    success=False,
                    result="",
                    error=str(r),
                ))
            else:
                final.append(r)

        return final

    # ── Status display ─────────────────────────────────────────────────────

    def get_status(self) -> list[dict[str, Any]]:
        """Return status info of all subagents."""
        return [
            {"task_id": tid, **info}
            for tid, info in self._active.items()
        ]

    def show_status(self) -> None:
        """Display a Rich table of active/completed subagents."""
        if not self._active:
            self.console.print("  [dim]No subagents.[/dim]")
            return

        table = Table(
            title="🤖 Subagents",
            title_style="bold white",
            border_style="bright_black",
            show_lines=True,
        )
        table.add_column("Task", min_width=24)
        table.add_column("Status", min_width=12)
        table.add_column("Steps", min_width=8)

        for tid, info in self._active.items():
            status_text = Text(info["status"])
            if "Done" in info["status"]:
                status_text.stylize("green")
            elif "Failed" in info["status"]:
                status_text.stylize("red")
            else:
                status_text.stylize("cyan")
            table.add_row(info["task"], status_text, str(info["steps"]))

        self.console.print(table)

    # ── Internal ───────────────────────────────────────────────────────────

    async def _run_subagent(
        self,
        task_id: str,
        instruction: str,
        tools: list[str] | None,
        context: str | None,
    ) -> SubagentResult:
        """
        Run a simplified agent loop for a subtask.

        This is a lightweight version of the main AgentLoop,
        limited in scope and tool access.
        """
        from nexcode.agent.context import AgentContext

        sub_context = AgentContext()

        # Build focused system prompt.
        system = (
            "You are a focused subagent working on a specific subtask. "
            "Complete the task efficiently and report your results.\n"
        )
        if context:
            system += f"\nContext: {context}\n"

        messages = [{"role": "user", "content": instruction}]
        steps_taken = 0
        files_modified: list[str] = []
        max_steps = 20  # Subagents have a lower step limit.

        for step_num in range(1, max_steps + 1):
            self._active[task_id]["steps"] = step_num

            # Get available tool schemas (filtered if specified).
            schemas = self.tool_registry.get_api_schemas()
            if tools:
                schemas = [s for s in schemas if s["function"]["name"] in tools]

            try:
                response = await self.ai_provider.chat(
                    messages=messages,
                    system=system,
                    tools=schemas,
                )
            except Exception as exc:
                return SubagentResult(
                    task_id=task_id,
                    success=False,
                    result="",
                    steps_taken=step_num,
                    error=f"AI error: {exc}",
                )

            # Check for tool calls.
            tool_calls = getattr(response, "tool_calls", []) or []
            content = getattr(response, "content", "") or ""

            if not tool_calls:
                # AI returned text only — task complete.
                return SubagentResult(
                    task_id=task_id,
                    success=True,
                    result=content,
                    steps_taken=step_num,
                    files_modified=files_modified,
                )

            # Process tool calls.
            messages.append({"role": "assistant", "content": response.content, "tool_calls": tool_calls})

            async def _run_tool(tc: Any) -> tuple[Any, str, dict[str, Any], str, Any]:
                tool_name = getattr(tc, "name", "") or tc.get("name", "")
                tool_input = getattr(tc, "input", {}) or tc.get("input", {})
                tool_id = getattr(tc, "id", "") or tc.get("id", "")
                result = await self.tool_registry.execute(tool_name, tool_input)
                return tc, tool_name, tool_input, tool_id, result

            tool_results = await asyncio.gather(*(_run_tool(tc) for tc in tool_calls))

            for tc, tool_name, tool_input, tool_id, result in tool_results:
                steps_taken += 1

                # Track file modifications.
                if hasattr(result, "success") and result.success:
                    path = tool_input.get("path", tool_input.get("source", ""))
                    if path and tool_name in ("write_file", "edit_file", "create_file"):
                        files_modified.append(str(path))

                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": str(getattr(result, "output", result)),
                        }
                    ],
                })

        return SubagentResult(
            task_id=task_id,
            success=True,
            result="Max steps reached.",
            steps_taken=max_steps,
            files_modified=files_modified,
        )

    @property
    def active_count(self) -> int:
        return sum(1 for info in self._active.values() if "Running" in info["status"])
