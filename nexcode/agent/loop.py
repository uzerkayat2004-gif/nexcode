"""
NexCode Agentic Loop
~~~~~~~~~~~~~~~~~~~~~

The brain of NexCode.  Receives an instruction, thinks, uses tools,
observes results, and keeps iterating until the task is complete.
Also includes task history for logging and replay.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from nexcode.agent.context import AgentContext
from nexcode.agent.observer import ResultObserver
from nexcode.agent.planner import TaskPlanner
from nexcode.agent.thinking import ThinkingDisplay

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HISTORY_DIR = Path.home() / ".nexcode" / "task_history"
_DEFAULT_MAX_STEPS = 50


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AgentStep:
    """Record of a single step in the agentic loop."""

    step_number: int
    thought: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_result: Any = None
    ai_response: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int = 0


@dataclass
class AgentTask:
    """A complete task record."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    instruction: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "running"  # running, completed, failed, paused, aborted
    steps_taken: int = 0
    tools_used: list[str] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    files_modified: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------

class AgentLoop:
    """
    Core agentic loop for NexCode.

    Implements the think → act → observe cycle:
    1. Send instruction + history to AI
    2. AI returns text (done) or tool call (act)
    3. Execute tool, send result back
    4. Repeat until done, stuck, or aborted
    """

    def __init__(
        self,
        ai_provider: Any,
        tool_registry: Any,
        context: AgentContext | None = None,
        console: Console | None = None,
    ) -> None:
        self.ai_provider = ai_provider
        self.tool_registry = tool_registry
        self.context = context or AgentContext()
        self.console = console or Console()

        self.display = ThinkingDisplay(self.console)
        self.observer = ResultObserver()
        self.planner = TaskPlanner(self.console)

        self._current_task: AgentTask | None = None
        self._steps: list[AgentStep] = []
        self._paused = False
        self._aborted = False

    # ── Main entry point ───────────────────────────────────────────────────

    async def run(
        self,
        instruction: str,
        max_steps: int = _DEFAULT_MAX_STEPS,
    ) -> AgentTask:
        """
        Run a task to completion.

        Args:
            instruction: The user's instruction.
            max_steps: Safety limit on iterations.

        Returns:
            An ``AgentTask`` with the final status and result.
        """
        # Create task record.
        task = AgentTask(instruction=instruction)
        self._current_task = task
        self._steps.clear()
        self._paused = False
        self._aborted = False

        # Optional: generate and show plan for complex tasks.
        if self.planner.should_plan(instruction):
            try:
                plan = await self.planner.create_plan(
                    instruction, self.ai_provider,
                    context_summary=self.context.get_project_summary(),
                )
                approved = self.planner.show_plan(plan)
                if not approved:
                    task.status = "aborted"
                    task.result = "User cancelled the plan."
                    return task

                # Inject plan into context.
                plan_context = self.planner.plan_to_context(plan)
                self.context.add_message(
                    "user",
                    f"{instruction}\n\nHere is the approved plan:\n{plan_context}",
                )
            except Exception:
                # Plan generation failed — proceed without plan.
                self.context.add_message("user", instruction)
        else:
            self.context.add_message("user", instruction)

        # ── Core loop ──────────────────────────────────────────────────────
        for step_num in range(1, max_steps + 1):
            if self._aborted:
                task.status = "aborted"
                task.error = "Aborted by user."
                break

            if self._paused:
                task.status = "paused"
                break

            # Check context size.
            if self.context.needs_compaction():
                self.console.print("  [yellow]Context getting full — compacting...[/]")
                try:
                    msg = await self.context.compact(self.ai_provider)
                    self.console.print(f"  [dim]{msg}[/]")
                except Exception:
                    pass

            # Display step.
            self.display.show_step(step_num, max_steps)

            # Call AI.
            step = AgentStep(step_number=step_num)
            import time
            start = time.perf_counter()

            try:
                with self.display.show_thinking(step_num):
                    response = await self.ai_provider.chat(
                        messages=self.context.get_messages(),
                        system=self.context.get_system_prompt(),
                        tools=self.tool_registry.get_api_schemas(),
                    )
            except KeyboardInterrupt:
                self._handle_interrupt(task, step_num)
                if self._aborted:
                    break
                if self._paused:
                    break
                continue
            except Exception as exc:
                step.duration_ms = int((time.perf_counter() - start) * 1000)
                self.display.show_error(f"AI error: {exc}")
                task.status = "failed"
                task.error = str(exc)
                break

            step.duration_ms = int((time.perf_counter() - start) * 1000)

            # Extract content and tool calls.
            content = getattr(response, "content", "") or ""
            tool_calls = getattr(response, "tool_calls", []) or []

            # ── No tool calls → task complete ──────────────────────────────
            if not tool_calls:
                step.ai_response = content
                self._steps.append(step)
                task.steps_taken = step_num

                # Show AI's final response.
                if content:
                    self.display.show_ai_response(content)

                # Add to context.
                self.context.add_message("assistant", content)

                task.status = "completed"
                task.result = content
                break

            # ── Process tool calls ─────────────────────────────────────────
            # Add assistant message with tool calls to context.
            self.context.add_message("assistant", response.content if hasattr(response, "content") else content)

            for tc in tool_calls:
                tool_name = getattr(tc, "name", "") or (tc.get("name", "") if isinstance(tc, dict) else "")
                tool_input = getattr(tc, "input", {}) or (tc.get("input", {}) if isinstance(tc, dict) else {})
                tool_id = getattr(tc, "id", "") or (tc.get("id", "") if isinstance(tc, dict) else "")

                step.tool_name = tool_name
                step.tool_input = tool_input

                # Display the tool call.
                self.display.show_tool_call(tool_name, tool_input)

                # Execute the tool.
                try:
                    result = await self.tool_registry.execute(tool_name, tool_input)
                except KeyboardInterrupt:
                    self._handle_interrupt(task, step_num)
                    break
                except Exception as exc:
                    from nexcode.tools.base import ToolResult
                    result = ToolResult.fail(f"Execution error: {exc}")

                step.tool_result = result

                # Display result.
                self.display.show_tool_result(tool_name, result)

                # Track tool usage.
                if tool_name not in task.tools_used:
                    task.tools_used.append(tool_name)

                # Track file modifications.
                if hasattr(result, "success") and result.success:
                    path = tool_input.get("path", tool_input.get("source", ""))
                    if path and tool_name in (
                        "write_file", "edit_file", "create_file",
                        "delete_file", "move_file", "copy_file",
                    ):
                        self.context.track_file_modified(str(path))
                        if str(path) not in task.files_modified:
                            task.files_modified.append(str(path))

                # Send result back to AI.
                self.context.add_tool_result(tool_id, result)

                # Observe and check for stuck patterns.
                self._steps.append(step)
                if self.observer.is_stuck(self._steps):
                    reason = self.observer.get_stuck_reason(self._steps)
                    suggestion = self.observer.suggest_recovery(self._steps)
                    self.console.print(f"\n  [yellow]⚠️  Agent appears stuck: {reason}[/]")
                    self.console.print(f"  [dim]{suggestion}[/]\n")

                    # Ask user what to do.
                    try:
                        choice = input("  [c]ontinue / [s]top / [r]ephrase > ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        choice = "s"

                    if choice == "s":
                        task.status = "failed"
                        task.error = f"Agent stuck: {reason}"
                        self._aborted = True
                        break
                    elif choice == "r":
                        try:
                            new_instruction = input("  New instruction > ")
                            self.context.add_message("user", new_instruction)
                        except (EOFError, KeyboardInterrupt):
                            pass

                # Create new step for next tool call.
                step = AgentStep(step_number=step_num)

            if self._aborted:
                break

            task.steps_taken = step_num

        else:
            # Reached max_steps.
            task.status = "failed"
            task.error = f"Reached maximum step limit ({max_steps})"
            self.console.print(
                f"\n  [yellow]⚠️  Reached max steps ({max_steps}). "
                f"Task may be incomplete.[/]\n"
            )

        # Show completion or failure.
        if task.status == "completed":
            self.display.show_completion(task)
        elif task.status in ("failed", "aborted"):
            self.display.show_aborted(task.error or "Unknown", task.steps_taken)

        # Save to history.
        TaskHistory.save(task)

        self._current_task = None
        return task

    # ── Pause / Resume / Abort ─────────────────────────────────────────────

    async def pause(self) -> None:
        """Pause the running task."""
        self._paused = True

    async def resume(self) -> None:
        """Resume a paused task."""
        if self._current_task and self._current_task.status == "paused":
            self._paused = False
            self._current_task.status = "running"

    async def abort(self) -> None:
        """Abort the running task immediately."""
        self._aborted = True

    # ── Status ─────────────────────────────────────────────────────────────

    def get_status(self) -> AgentTask | None:
        return self._current_task

    def get_steps(self) -> list[AgentStep]:
        return list(self._steps)

    # ── Interrupt handler ──────────────────────────────────────────────────

    def _handle_interrupt(self, task: AgentTask, steps_taken: int) -> None:
        """Handle Ctrl+C during task execution."""
        self.display.show_interrupt_menu(steps_taken)

        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = "s"

        if choice == "r":
            # Resume — continue the loop.
            pass
        elif choice == "s":
            task.status = "aborted"
            task.error = "Stopped by user."
            self._aborted = True
        elif choice == "u":
            # Undo all changes.
            files = self.context.get_files_modified()
            if files:
                self.console.print(f"  [yellow]Undoing changes to {len(files)} file(s)...[/]")
                try:
                    from nexcode.tools.base import CheckpointManager
                    cm = CheckpointManager()
                    for path in files:
                        checkpoints = cm.list_checkpoints(path)
                        if checkpoints:
                            cm.restore(checkpoints[0]["id"])
                            self.console.print(f"  [green]Restored: {path}[/]")
                except Exception as exc:
                    self.console.print(f"  [red]Undo failed: {exc}[/]")
            task.status = "aborted"
            task.error = "Undone by user."
            self._aborted = True
        elif choice == "q":
            task.status = "aborted"
            task.error = "User quit."
            self._aborted = True
            raise SystemExit(0)


# ---------------------------------------------------------------------------
# TaskHistory
# ---------------------------------------------------------------------------

class TaskHistory:
    """Persists completed tasks for review and replay."""

    @staticmethod
    def save(task: AgentTask) -> None:
        """Save a completed task to history."""
        _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        path = _HISTORY_DIR / f"{task.id}.json"

        data = {
            "id": task.id,
            "instruction": task.instruction,
            "created_at": task.created_at.isoformat(),
            "status": task.status,
            "steps_taken": task.steps_taken,
            "tools_used": task.tools_used,
            "result": task.result,
            "error": task.error,
            "files_modified": task.files_modified,
        }

        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    @staticmethod
    def get_recent(limit: int = 20) -> list[dict[str, Any]]:
        """Load recent tasks from history."""
        if not _HISTORY_DIR.exists():
            return []

        files = sorted(_HISTORY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        tasks: list[dict[str, Any]] = []

        for f in files[:limit]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                tasks.append(data)
            except (json.JSONDecodeError, OSError):
                continue

        return tasks

    @staticmethod
    def show(console: Console | None = None) -> None:
        """Display task history in a Rich table."""
        from rich.table import Table

        console = console or Console()
        tasks = TaskHistory.get_recent(20)

        if not tasks:
            console.print("  [dim]No task history.[/dim]")
            return

        table = Table(
            title="📜 Task History",
            title_style="bold white",
            border_style="bright_black",
            show_lines=True,
        )
        table.add_column("Time", min_width=10)
        table.add_column("Task", min_width=30, max_width=50)
        table.add_column("Status", min_width=8)
        table.add_column("Steps", min_width=6)

        for t in tasks:
            created = t.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created)
                from nexcode.git.history import _relative_time
                age = _relative_time(dt)
            except Exception:
                age = created[:16]

            status = t.get("status", "?")
            icon = {"completed": "✅", "failed": "❌", "aborted": "⚠️"}.get(status, "❓")
            instruction = t.get("instruction", "")[:50]
            steps = str(t.get("steps_taken", 0))

            table.add_row(age, instruction, f"{icon} {status}", steps)

        console.print()
        console.print(table)
        console.print()
