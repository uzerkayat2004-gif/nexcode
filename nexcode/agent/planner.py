"""
NexCode Task Planner
~~~~~~~~~~~~~~~~~~~~~

Generates execution plans for complex tasks, displays them
with Rich formatting, and handles user approval before execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PlanStep:
    """A single step in a task plan."""

    number: int
    description: str
    tools_needed: list[str] = field(default_factory=list)
    can_be_parallelized: bool = False


@dataclass
class TaskPlan:
    """A full task plan with steps, estimates, and risk assessment."""

    title: str
    steps: list[PlanStep] = field(default_factory=list)
    estimated_tool_calls: int = 0
    risk_level: str = "low"  # "low", "medium", "high"
    files_to_modify: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Complexity keywords for should_plan heuristic
# ---------------------------------------------------------------------------

_COMPLEX_KEYWORDS = [
    "refactor", "rewrite", "migrate", "redesign", "implement",
    "build", "create a full", "add authentication", "set up",
    "multiple files", "every file", "all files", "entire",
    "step by step", "comprehensive", "complete", "overhaul",
    "database", "api", "backend", "frontend", "full stack",
]

_SIMPLE_KEYWORDS = [
    "fix this", "what is", "explain", "how do i", "read",
    "show me", "print", "find", "search for", "where is",
    "quick", "small", "typo", "rename", "delete this",
]


# ---------------------------------------------------------------------------
# TaskPlanner
# ---------------------------------------------------------------------------

class TaskPlanner:
    """
    Generates execution plans for complex multi-step tasks.

    Uses heuristics to determine if planning is needed, then
    asks the AI to produce a structured plan for user approval.
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    # ── Complexity check ───────────────────────────────────────────────────

    def should_plan(self, instruction: str) -> bool:
        """
        Heuristic: does this instruction need a plan?

        Returns True for complex multi-step tasks,
        False for simple single-step tasks.
        """
        instruction_lower = instruction.lower()

        # Definitely simple.
        if any(kw in instruction_lower for kw in _SIMPLE_KEYWORDS):
            return False

        # Definitely complex.
        if any(kw in instruction_lower for kw in _COMPLEX_KEYWORDS):
            return True

        # Length-based heuristic: longer instructions are more complex.
        if len(instruction.split()) > 30:
            return True

        return False

    # ── Plan generation ────────────────────────────────────────────────────

    async def create_plan(
        self,
        instruction: str,
        ai_provider: Any,
        context_summary: str = "",
    ) -> TaskPlan:
        """
        Use the AI to generate a structured task plan.

        Falls back to a simple single-step plan if AI fails.
        """
        plan_prompt = (
            "Create a brief execution plan for this task. "
            "List numbered steps, each with: description and tools needed. "
            "Also estimate risk level (low/medium/high) and files to modify.\n\n"
            f"Task: {instruction}\n"
        )
        if context_summary:
            plan_prompt += f"\nProject context: {context_summary}\n"

        try:
            response = await ai_provider.chat(
                messages=[{"role": "user", "content": plan_prompt}],
                system="You are a task planner. Output concise numbered plans.",
            )
            content = response.content if hasattr(response, "content") else str(response)
            return self._parse_plan_response(instruction, content)
        except Exception:
            # Fallback: single-step plan.
            return TaskPlan(
                title=instruction[:60],
                steps=[PlanStep(number=1, description=instruction, tools_needed=[])],
                estimated_tool_calls=5,
                risk_level="low",
            )

    # ── Plan display ───────────────────────────────────────────────────────

    def show_plan(self, plan: TaskPlan) -> bool:
        """
        Display the plan and ask user for approval.

        Returns True if approved, False if rejected.
        """
        body = Text()

        for step in plan.steps:
            body.append(f"  Step {step.number}  ", style="bold white")
            body.append(step.description + "\n", style="white")
            if step.tools_needed:
                body.append(f"          Tools: {', '.join(step.tools_needed)}\n", style="dim")
            body.append("\n")

        # Footer with stats.
        risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(plan.risk_level, "white")
        footer = Text()
        footer.append(f"  Risk: ", style="dim")
        footer.append(plan.risk_level.capitalize(), style=risk_color)
        footer.append(f"  │  ~{plan.estimated_tool_calls} tool calls", style="dim")
        if plan.files_to_modify:
            footer.append(f"  │  {len(plan.files_to_modify)} files", style="dim")
        body.append(footer)

        self.console.print(
            Panel(
                body,
                title=f" 📋 Task Plan: {plan.title[:50]} ",
                title_align="left",
                border_style="bright_blue",
                padding=(1, 1),
            )
        )

        # Approval prompt.
        self.console.print("  [bold][y][/] Start   [bold][e][/] Edit plan   [bold][n][/] Cancel")
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False

        return choice in ("y", "yes", "")

    # ── Plan as context ────────────────────────────────────────────────────

    def plan_to_context(self, plan: TaskPlan) -> str:
        """Convert a plan into a context string for the AI."""
        lines = [f"Task Plan: {plan.title}\n"]
        for step in plan.steps:
            tools_str = f" (tools: {', '.join(step.tools_needed)})" if step.tools_needed else ""
            lines.append(f"  {step.number}. {step.description}{tools_str}")
        lines.append(f"\nRisk: {plan.risk_level} | Est. tool calls: {plan.estimated_tool_calls}")
        return "\n".join(lines)

    # ── Internal ───────────────────────────────────────────────────────────

    def _parse_plan_response(self, instruction: str, response: str) -> TaskPlan:
        """Parse the AI's plan response into a TaskPlan."""
        steps: list[PlanStep] = []
        lines = response.strip().splitlines()

        step_num = 0
        for line in lines:
            stripped = line.strip()
            # Look for numbered lines: "1. ...", "1) ...", "Step 1: ..."
            for prefix_pattern in [f"{step_num + 1}.", f"{step_num + 1})", f"Step {step_num + 1}"]:
                if stripped.startswith(prefix_pattern):
                    step_num += 1
                    desc = stripped[len(prefix_pattern):].strip().lstrip(":").strip()
                    steps.append(PlanStep(number=step_num, description=desc))
                    break

        if not steps:
            steps = [PlanStep(number=1, description=instruction)]

        # Estimate risk based on step count and keywords.
        risk = "low"
        instruction_lower = instruction.lower()
        if any(kw in instruction_lower for kw in ["delete", "drop", "remove", "reset", "rewrite"]):
            risk = "high"
        elif len(steps) > 5 or any(kw in instruction_lower for kw in ["refactor", "migrate", "overhaul"]):
            risk = "medium"

        return TaskPlan(
            title=instruction[:60],
            steps=steps,
            estimated_tool_calls=len(steps) * 3,
            risk_level=risk,
        )
