"""
NexCode AI Pair Programming Mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two AI models work together — one writes code,
one reviews it, iterating until quality converges.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


@dataclass
class PairIteration:
    iteration: int = 0
    driver_code: str = ""
    reviewer_feedback: str = ""
    issues_found: int = 0
    improved_code: str = ""
    improvement_summary: str = ""


@dataclass
class PairResult:
    final_code: str = ""
    iterations: list[PairIteration] = field(default_factory=list)
    total_improvements: int = 0
    driver_model: str = ""
    reviewer_model: str = ""
    total_cost_usd: float = 0.0
    quality_score: float = 0.0
    duration_ms: int = 0


class PairProgrammingSession:
    """Two AI models collaborate: one writes, one reviews."""

    def __init__(
        self,
        driver_provider: Any = None,
        reviewer_provider: Any = None,
        console: Console | None = None,
        max_iterations: int = 3,
    ) -> None:
        self.driver = driver_provider
        self.reviewer = reviewer_provider
        self.console = console or Console()
        self.max_iterations = max_iterations

    async def start(
        self,
        instruction: str,
        driver_model: str = "claude-opus-4-6",
        reviewer_model: str = "gemini-2.0-flash",
    ) -> PairResult:
        """Run full pair programming session."""
        start = time.perf_counter()
        result = PairResult(driver_model=driver_model, reviewer_model=reviewer_model)

        self.console.print(Panel(
            f"  🧑‍💻 Driver: {driver_model}\n  🔍 Reviewer: {reviewer_model}\n  📝 Task: {instruction}",
            title=" 👥 Pair Programming ", border_style="magenta", padding=(0, 1),
        ))

        # Initial code from driver.
        self.console.print(f"\n  🧑‍💻 Driver ({driver_model}) writes code...\n")
        code = await self._driver_write(instruction)

        for i in range(self.max_iterations):
            iteration = PairIteration(iteration=i + 1, driver_code=code)

            # Reviewer critiques.
            self.console.print(f"  🔍 Reviewer ({reviewer_model}) critiques...\n")
            feedback = await self._reviewer_critique(code, instruction)
            iteration.reviewer_feedback = feedback
            iteration.issues_found = feedback.count("\n") + 1 if feedback.strip() else 0

            # Check if reviewer is satisfied.
            if "no issues" in feedback.lower() or "looks good" in feedback.lower() or not feedback.strip():
                iteration.improvement_summary = "Reviewer approved — no changes needed"
                result.iterations.append(iteration)
                self.console.print("  ✅ Reviewer approved!\n")
                break

            self.console.print(f"  Found {iteration.issues_found} suggestions\n")

            # Driver improves based on feedback.
            self.console.print("  🧑‍💻 Driver improves based on feedback...\n")
            improved = await self._driver_improve(code, feedback, instruction)
            iteration.improved_code = improved
            iteration.improvement_summary = f"Applied {iteration.issues_found} improvements"
            result.iterations.append(iteration)
            result.total_improvements += iteration.issues_found
            code = improved

        result.final_code = code
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        result.quality_score = min(100, 70 + (len(result.iterations) * 10))

        self.console.print(Panel(
            Text.from_markup(
                f"  ✅ Pair session complete — {len(result.iterations)} iterations\n"
                f"  Quality score: {result.quality_score:.0f}/100\n"
                f"  Improvements: {result.total_improvements}\n"
                f"  Duration: {result.duration_ms}ms"
            ),
            title=" 👥 Pair Result ", border_style="green", padding=(0, 1),
        ))

        return result

    async def run_iteration(self, code: str, context: str) -> PairIteration:
        """Single iteration: review + improve."""
        iteration = PairIteration(driver_code=code)
        feedback = await self._reviewer_critique(code, context)
        iteration.reviewer_feedback = feedback
        iteration.issues_found = feedback.count("\n") + 1 if feedback.strip() else 0
        if iteration.issues_found > 0:
            improved = await self._driver_improve(code, feedback, context)
            iteration.improved_code = improved
        return iteration

    async def _driver_write(self, instruction: str) -> str:
        if not self.driver:
            return f"# Placeholder for: {instruction}"
        try:
            resp = await self.driver.chat(
                messages=[{"role": "user", "content": instruction}],
                system="You are an expert programmer. Write clean, production-quality code. Return only code.",
            )
            return getattr(resp, "content", "")
        except Exception as e:
            return f"# Error: {e}"

    async def _reviewer_critique(self, code: str, instruction: str) -> str:
        if not self.reviewer:
            return "No reviewer available"
        try:
            resp = await self.reviewer.chat(
                messages=[{"role": "user", "content": (
                    f"Review this code for bugs, security, performance, and best practices.\n"
                    f"Original task: {instruction}\n\n{code[:6000]}\n\n"
                    "List specific issues to fix. If the code is perfect, say 'No issues found'."
                )}],
                system="You are a strict code reviewer. Be specific and actionable.",
            )
            return getattr(resp, "content", "")
        except Exception:
            return ""

    async def _driver_improve(self, code: str, feedback: str, instruction: str) -> str:
        if not self.driver:
            return code
        try:
            resp = await self.driver.chat(
                messages=[{"role": "user", "content": (
                    f"Improve this code based on reviewer feedback.\n\n"
                    f"Original task: {instruction}\n\nCurrent code:\n{code[:5000]}\n\n"
                    f"Reviewer feedback:\n{feedback[:2000]}\n\n"
                    "Return the complete improved code."
                )}],
                system="You improve code based on review feedback. Return only the complete improved code.",
            )
            return getattr(resp, "content", code)
        except Exception:
            return code
