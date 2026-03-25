"""
NexCode Multi-Model Comparison Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the same prompt on multiple models simultaneously,
AI-judge the results, and display side-by-side.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.table import Table


@dataclass
class ModelResponse:
    provider: str = ""
    model: str = ""
    response: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    quality_score: float | None = None


@dataclass
class ComparisonResult:
    instruction: str = ""
    responses: list[ModelResponse] = field(default_factory=list)
    winner: ModelResponse | None = None
    analysis: str = ""
    recommendation: str = ""


@dataclass
class BenchmarkResult:
    task: str = ""
    results: list[ModelResponse] = field(default_factory=list)
    rankings: list[str] = field(default_factory=list)


class ModelComparator:
    """Run same prompt on multiple models and compare."""

    def __init__(self, ai_providers: dict[str, Any] | None = None, console: Console | None = None) -> None:
        self.providers = ai_providers or {}
        self.console = console or Console()

    async def compare(
        self,
        instruction: str,
        models: list[tuple[str, str]] | None = None,
        auto_judge: bool = True,
    ) -> ComparisonResult:
        """Run same prompt on multiple models simultaneously."""
        if not models:
            models = list(self.providers.items())[:3] if self.providers else []

        result = ComparisonResult(instruction=instruction)

        async def _query(provider_name: str, model_name: str) -> ModelResponse:
            provider = self.providers.get(provider_name)
            if not provider:
                return ModelResponse(provider=provider_name, model=model_name, response="Provider not available")
            start = time.perf_counter()
            try:
                resp = await provider.chat(
                    messages=[{"role": "user", "content": instruction}],
                    model=model_name,
                )
                elapsed = int((time.perf_counter() - start) * 1000)
                text = getattr(resp, "content", str(resp))
                tokens = getattr(resp, "usage", {}).get("total_tokens", len(text) // 4)
                return ModelResponse(
                    provider=provider_name, model=model_name,
                    response=text, tokens_used=tokens, duration_ms=elapsed,
                )
            except Exception as e:
                return ModelResponse(provider=provider_name, model=model_name, response=f"Error: {e}")

        tasks = [_query(p, m) for p, m in models]
        result.responses = await asyncio.gather(*tasks)

        if auto_judge and len(result.responses) > 1:
            await self._judge(result)

        return result

    async def benchmark(self, task: str, models: list[tuple[str, str]]) -> BenchmarkResult:
        """Benchmark models on a coding task."""
        comparison = await self.compare(task, models)
        ranked = sorted(comparison.responses, key=lambda r: r.quality_score or 0, reverse=True)
        return BenchmarkResult(
            task=task, results=ranked,
            rankings=[f"{r.model} ({r.quality_score or 0:.0f})" for r in ranked],
        )

    def show_comparison(self, result: ComparisonResult) -> None:
        """Show side-by-side comparison."""
        table = Table(title=f" ⚖️  Model Comparison ", border_style="cyan", show_lines=True)
        for r in result.responses:
            table.add_column(r.model, style="white", max_width=40)

        # Response row.
        table.add_row(*[r.response[:200] + "..." if len(r.response) > 200 else r.response for r in result.responses])

        # Stats row.
        stats = []
        for r in result.responses:
            score = f"⭐ {r.quality_score:.0f}" if r.quality_score else "—"
            cost = f"${r.cost_usd:.4f}" if r.cost_usd > 0 else "FREE"
            stats.append(f"{score}  💰 {cost}  ⏱ {r.duration_ms}ms")
        table.add_row(*stats)

        self.console.print(table)

        if result.winner:
            self.console.print(f"\n  🏆 Winner: [bold]{result.winner.model}[/]\n")
        if result.recommendation:
            self.console.print(f"  💡 {result.recommendation}\n")

    async def user_pick(self, result: ComparisonResult) -> ModelResponse | None:
        """Let user pick best response."""
        self.show_comparison(result)
        for i, r in enumerate(result.responses, 1):
            self.console.print(f"  [{i}] Use {r.model}")
        try:
            choice = int(input("  › ").strip()) - 1
            if 0 <= choice < len(result.responses):
                return result.responses[choice]
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
        return None

    async def _judge(self, result: ComparisonResult) -> None:
        """AI judge the responses."""
        judge = next(iter(self.providers.values()), None)
        if not judge:
            return
        try:
            responses_text = "\n\n".join(
                f"Model {i+1} ({r.model}):\n{r.response[:1000]}"
                for i, r in enumerate(result.responses)
            )
            prompt = (
                f"Task: {result.instruction}\n\n{responses_text}\n\n"
                "Rate each response 0-100. Return: MODEL_NUM:SCORE on each line."
            )
            resp = await judge.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You are a code quality judge. Rate responses 0-100.",
            )
            text = getattr(resp, "content", str(resp))
            for line in text.splitlines():
                if ":" in line:
                    parts = line.split(":")
                    try:
                        idx = int(parts[0].strip().split()[-1]) - 1
                        score = float(parts[1].strip().split()[0])
                        if 0 <= idx < len(result.responses):
                            result.responses[idx].quality_score = score
                    except (ValueError, IndexError):
                        continue
            best = max(result.responses, key=lambda r: r.quality_score or 0)
            result.winner = best
        except Exception:
            pass
