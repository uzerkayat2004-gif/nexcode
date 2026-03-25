"""
NexCode Smart Cost Optimizer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Auto-routes tasks to the cheapest capable model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.table import Table

TASK_COMPLEXITY_RULES: dict[str, list[str]] = {
    "simple": [
        "rename", "fix typo", "add comment", "format code", "one-liner",
        "change variable", "update string", "remove line", "add import",
    ],
    "medium": [
        "write a function", "fix a bug", "add error handling", "write tests",
        "add validation", "refactor", "create class", "update endpoint",
    ],
    "complex": [
        "architect", "refactor entire", "debug race condition", "design schema",
        "security audit", "full implementation", "migrate", "rewrite",
    ],
}

MODEL_TIERS: dict[str, list[tuple[str, str, float]]] = {
    "simple": [
        ("google", "gemini-2.0-flash", 0.0),
        ("openrouter", "kimi-k2.5", 0.0),
        ("groq", "llama-3.1-8b", 0.0),
    ],
    "medium": [
        ("openrouter", "kimi-k2.5", 0.0),
        ("google", "gemini-2.0-flash", 0.0),
        ("deepseek", "deepseek-chat", 0.001),
    ],
    "complex": [
        ("anthropic", "claude-opus-4-6", 0.015),
        ("openai", "gpt-4o", 0.005),
        ("google", "gemini-1.5-pro", 0.003),
    ],
}


@dataclass
class OptimizationSuggestion:
    current_model: str = ""
    suggested_model: str = ""
    suggested_provider: str = ""
    reason: str = ""
    estimated_savings_pct: float = 0.0
    quality_tradeoff: str = "none"


class CostOptimizer:
    """Smart task routing to cheapest capable model."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self._session_costs: list[dict[str, Any]] = []

    async def suggest_model(
        self,
        instruction: str,
        quality_preference: str = "balanced",
    ) -> OptimizationSuggestion:
        """Suggest cheapest model that can handle the task."""
        complexity = self._classify(instruction)
        tier = MODEL_TIERS.get(complexity, MODEL_TIERS["medium"])

        if quality_preference == "quality":
            tier = MODEL_TIERS["complex"]
        elif quality_preference == "economy":
            tier = MODEL_TIERS["simple"]

        if not tier:
            return OptimizationSuggestion(reason="No models available")

        best = tier[0]
        return OptimizationSuggestion(
            suggested_provider=best[0],
            suggested_model=best[1],
            reason=f"Task classified as '{complexity}' — {best[1]} is optimal",
            estimated_savings_pct=80 if best[2] == 0 else 0,
            quality_tradeoff="none" if complexity != "complex" else "moderate",
        )

    async def auto_route(self, instruction: str) -> tuple[str, str]:
        """Return (provider, model) for the task."""
        suggestion = await self.suggest_model(instruction)
        return suggestion.suggested_provider, suggestion.suggested_model

    def track_cost(self, model: str, provider: str, tokens: int, cost: float) -> None:
        self._session_costs.append({"model": model, "provider": provider, "tokens": tokens, "cost": cost})

    def show_cost_report(self) -> None:
        """Show session cost breakdown."""
        if not self._session_costs:
            self.console.print("  [dim]No costs recorded this session[/]")
            return
        table = Table(title=" 💰 Session Cost Breakdown ", border_style="green")
        table.add_column("Model"); table.add_column("Calls"); table.add_column("Tokens"); table.add_column("Cost")

        by_model: dict[str, dict[str, Any]] = {}
        for c in self._session_costs:
            key = c["model"]
            if key not in by_model:
                by_model[key] = {"calls": 0, "tokens": 0, "cost": 0.0}
            by_model[key]["calls"] += 1
            by_model[key]["tokens"] += c["tokens"]
            by_model[key]["cost"] += c["cost"]

        total = 0.0
        for model, stats in by_model.items():
            total += stats["cost"]
            cost_str = f"${stats['cost']:.4f}" if stats["cost"] > 0 else "FREE"
            table.add_row(model, str(stats["calls"]), f"{stats['tokens']:,}", cost_str)

        self.console.print(table)
        self.console.print(f"\n  Total: ${total:.4f}\n")

    async def estimate_cost(self, instruction: str, model: str, provider: str) -> float:
        """Rough cost estimate for a task."""
        words = len(instruction.split())
        tokens_est = words * 4
        rates = {"claude-opus-4-6": 0.015, "gpt-4o": 0.005, "gemini-1.5-pro": 0.003}
        rate = rates.get(model, 0.0)
        return (tokens_est / 1000) * rate

    async def find_free_alternatives(self, instruction: str) -> list[tuple[str, str]]:
        """Find free models for the task."""
        return [
            ("google", "gemini-2.0-flash"),
            ("openrouter", "kimi-k2.5"),
            ("groq", "llama-3.1-8b"),
        ]

    def _classify(self, instruction: str) -> str:
        lower = instruction.lower()
        for level, keywords in TASK_COMPLEXITY_RULES.items():
            if any(kw in lower for kw in keywords):
                return level
        return "medium"
