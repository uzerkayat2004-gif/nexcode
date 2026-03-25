"""
NexCode Thinking Display
~~~~~~~~~~~~~~~~~~~~~~~~~~

Rich-formatted display for the AI's reasoning process:
spinners, tool call panels, result summaries, step counters,
and task completion / abort displays.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text


class ThinkingDisplay:
    """
    Beautiful terminal display for every phase of the agentic loop.
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    # ── Step counter ───────────────────────────────────────────────────────

    def show_step(self, step: int, max_steps: int) -> None:
        """Display the current step number."""
        self.console.print(
            Rule(
                f" Step {step} / {max_steps} ",
                style="bright_black",
            )
        )

    # ── Tool call display ──────────────────────────────────────────────────

    def show_tool_call(self, tool_name: str, parameters: dict[str, Any]) -> None:
        """Show which tool is being called and its parameters."""
        body = Text()
        body.append(f"🔧 {tool_name}\n", style="bold cyan")

        for key, value in parameters.items():
            display_value = _truncate(str(value), 200)
            body.append(f"   {key}: ", style="dim")
            body.append(f'"{display_value}"\n', style="white")

        self.console.print(
            Panel(
                body,
                border_style="cyan",
                padding=(0, 1),
                expand=False,
            )
        )

    # ── Tool result display ────────────────────────────────────────────────

    def show_tool_result(self, tool_name: str, result: Any) -> None:
        """Show a summary of a tool's result."""
        success = getattr(result, "success", True)
        display = getattr(result, "display", str(result))
        error = getattr(result, "error", None)

        if success:
            icon = "✅"
            style = "green"
        else:
            icon = "❌"
            style = "red"

        text = Text()
        text.append(f" {icon} ", style=style)
        text.append(_truncate(str(display), 120), style=style)
        if error:
            text.append(f"\n    Error: {error}", style="bright_red")

        self.console.print(text)

    # ── AI response display ────────────────────────────────────────────────

    def show_ai_response(self, content: str) -> None:
        """Show the AI's text response to the user."""
        self.console.print()
        self.console.print(
            Panel(
                content,
                title=" NexCode ",
                title_align="left",
                border_style="bright_blue",
                padding=(1, 2),
            )
        )
        self.console.print()

    # ── Thinking indicator ─────────────────────────────────────────────────

    def show_thinking(self, step: int) -> Any:
        """
        Return a Rich Status context manager for a thinking spinner.

        Usage:
            with display.show_thinking(step) as status:
                ... # do work
        """
        return self.console.status(
            f"[bold cyan]Thinking (step {step})...[/]",
            spinner="dots",
            spinner_style="cyan",
        )

    # ── Task completion ────────────────────────────────────────────────────

    def show_completion(self, task: Any) -> None:
        """Show a task completion summary."""
        steps = getattr(task, "steps_taken", 0)
        tools = getattr(task, "tools_used", [])
        tid = getattr(task, "id", "?")

        body = Text()
        body.append(f"✅ Task completed in {steps} step(s)\n", style="bold green")
        if tools:
            unique = sorted(set(tools))
            body.append(f"   Tools used: {', '.join(unique)}\n", style="dim")
        body.append(f"   Task ID: {tid}", style="dim")

        self.console.print(
            Panel(
                body,
                border_style="green",
                padding=(0, 1),
            )
        )

    # ── Task aborted ───────────────────────────────────────────────────────

    def show_aborted(self, reason: str, steps_taken: int = 0) -> None:
        """Show that a task was aborted."""
        body = Text()
        body.append(f"⚠️  Task interrupted after {steps_taken} step(s)\n", style="yellow")
        body.append(f"   Reason: {reason}", style="dim")

        self.console.print(
            Panel(
                body,
                border_style="yellow",
                padding=(0, 1),
            )
        )

    # ── Error display ──────────────────────────────────────────────────────

    def show_error(self, message: str) -> None:
        """Show an error message."""
        self.console.print(f"  [bold red]Error:[/] {message}")

    # ── Plan display ───────────────────────────────────────────────────────

    def show_plan_step(self, step_num: int, description: str, tools: list[str]) -> None:
        """Show a single plan step."""
        tools_str = ", ".join(tools)
        text = Text()
        text.append(f"  Step {step_num}  ", style="bold white")
        text.append(description + "\n", style="white")
        text.append(f"          Tools: {tools_str}", style="dim")
        self.console.print(text)

    # ── Interrupt handler display ──────────────────────────────────────────

    def show_interrupt_menu(self, steps_taken: int) -> None:
        """Show the Ctrl+C interrupt options menu."""
        body = Text()
        body.append(f"⚠️  Task interrupted after {steps_taken} steps\n\n", style="yellow")
        body.append("  [r] Resume task\n", style="white")
        body.append("  [s] Stop and keep changes\n", style="white")
        body.append("  [u] Undo all changes from this task\n", style="red")
        body.append("  [q] Quit NexCode\n", style="dim")

        self.console.print(
            Panel(
                body,
                border_style="yellow",
                padding=(0, 1),
            )
        )

    # ── Subagent display ───────────────────────────────────────────────────

    def show_subagent_status(self, agents: list[dict[str, Any]]) -> None:
        """Show status of running subagents."""
        from rich.table import Table

        table = Table(
            title="🤖 Subagents",
            title_style="bold white",
            border_style="bright_black",
            show_lines=True,
        )
        table.add_column("Task", min_width=24)
        table.add_column("Status", min_width=10)
        table.add_column("Steps", min_width=8)

        for agent in agents:
            status_text = Text(agent.get("status", "?"))
            if "done" in agent.get("status", "").lower():
                status_text.stylize("green")
            else:
                status_text.stylize("cyan")
            table.add_row(
                agent.get("task", "?"),
                status_text,
                str(agent.get("steps", 0)),
            )

        self.console.print(table)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, max_len: int) -> str:
    """Truncate a string, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
