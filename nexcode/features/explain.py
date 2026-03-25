"""
NexCode Deep Code Explainer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Multi-depth code explanations with flow diagrams,
intent analysis, and error explanation.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


@dataclass
class Explanation:
    summary: str = ""
    detailed: str = ""
    key_concepts: list[str] = field(default_factory=list)
    diagram: str | None = None
    related_docs: list[str] = field(default_factory=list)


class CodeExplainer:
    """Multi-depth code explainer with diagrams."""

    def __init__(self, ai_provider: Any = None, console: Console | None = None) -> None:
        self.ai = ai_provider
        self.console = console or Console()

    async def explain(
        self,
        code: str | None = None,
        path: str | None = None,
        depth: str = "normal",
        audience: str = "developer",
    ) -> Explanation:
        """Explain code at different depth levels."""
        if path and not code:
            try:
                code = Path(path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return Explanation(summary=f"Cannot read {path}")

        if not code:
            return Explanation(summary="No code provided")

        depth_prompts = {
            "eli5": "Explain like I'm 5 years old. Use simple analogies.",
            "normal": "Give a clear explanation suitable for a developer.",
            "expert": "Technical deep-dive with implementation details, edge cases, and complexity analysis.",
            "line-by-line": "Explain each line of code with annotations.",
        }

        if not self.ai:
            return Explanation(
                summary=f"Code has {len(code.splitlines())} lines", detailed=code[:500]
            )

        try:
            prompt = (
                f"Explain this code. {depth_prompts.get(depth, depth_prompts['normal'])}\n"
                f"Audience: {audience}\n\n```\n{code[:6000]}\n```\n\n"
                "Provide: 1) One-line summary 2) Detailed explanation 3) Key concepts used"
            )
            resp = await self.ai.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You explain code clearly. Match the depth level and audience.",
            )
            text = getattr(resp, "content", "")
            lines = text.split("\n", 1)
            return Explanation(
                summary=lines[0][:200] if lines else "",
                detailed=text,
                key_concepts=self._extract_concepts(text),
            )
        except Exception as e:
            return Explanation(summary=f"Error: {e}")

    async def explain_flow(self, path: str) -> str:
        """Explain data flow through code."""
        try:
            code = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return f"Cannot read {path}"

        if not self.ai:
            return "AI provider needed for flow analysis"

        try:
            resp = await self.ai.chat(
                messages=[
                    {
                        "role": "user",
                        "content": f"Trace the data flow in this code:\n\n{code[:5000]}",
                    }
                ],
                system="Explain how data flows through the code, from input to output.",
            )
            return getattr(resp, "content", "")
        except Exception:
            return "Flow analysis failed"

    async def explain_intent(self, path: str) -> str:
        """Explain WHY code was written this way."""
        try:
            code = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return f"Cannot read {path}"

        if not self.ai:
            return "AI provider needed for intent analysis"

        try:
            resp = await self.ai.chat(
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Explain the INTENT behind this code — why was it written this way?\n\n{code[:5000]}"
                        ),
                    }
                ],
                system="You analyze code intent and design decisions. Explain the 'why', not the 'what'.",
            )
            return getattr(resp, "content", "")
        except Exception:
            return "Intent analysis failed"

    async def generate_diagram(self, path: str, diagram_type: str = "flow") -> str:
        """Generate ASCII diagram."""
        try:
            code = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return f"Cannot read {path}"

        if not self.ai:
            return "AI provider needed for diagram generation"

        try:
            resp = await self.ai.chat(
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Generate an ASCII {diagram_type} diagram for this code:\n\n{code[:4000]}"
                        ),
                    }
                ],
                system="Generate clean ASCII diagrams. Use box-drawing characters.",
            )
            diagram = getattr(resp, "content", "")
            self.console.print(
                Panel(diagram, title=f" 📊 {diagram_type.title()} Diagram ", border_style="cyan")
            )
            return diagram
        except Exception:
            return "Diagram generation failed"

    async def explain_error(self, error: str, context_file: str | None = None) -> str:
        """Explain an error message."""
        context = ""
        if context_file:
            try:
                context = (
                    f"\n\nRelated code:\n{Path(context_file).read_text(encoding='utf-8')[:3000]}"
                )
            except (OSError, UnicodeDecodeError):
                pass

        if not self.ai:
            return f"Error: {error}"

        try:
            resp = await self.ai.chat(
                messages=[
                    {
                        "role": "user",
                        "content": f"Explain this error and how to fix it:\n\n{error}{context}",
                    }
                ],
                system="You explain errors clearly. Include: what it means, why it happened, how to fix it.",
            )
            return getattr(resp, "content", "")
        except Exception:
            return f"Cannot explain: {error}"

    async def explain_diff(self, diff: str) -> str:
        """Explain a git diff in plain English."""
        if not self.ai:
            return "AI provider needed"
        try:
            resp = await self.ai.chat(
                messages=[
                    {
                        "role": "user",
                        "content": f"Explain this diff in plain English:\n\n{diff[:5000]}",
                    }
                ],
                system="Explain code diffs clearly. Say what changed and why it matters.",
            )
            return getattr(resp, "content", "")
        except Exception:
            return "Diff explanation failed"

    async def explain_history(self, commits: list[Any]) -> str:
        """Explain commit history."""
        if not self.ai:
            return "AI provider needed"
        commit_text = "\n".join(str(c)[:100] for c in commits[:20])
        try:
            resp = await self.ai.chat(
                messages=[
                    {"role": "user", "content": f"Summarize this commit history:\n\n{commit_text}"}
                ],
                system="Summarize git history into a narrative. What was the dev working on?",
            )
            return getattr(resp, "content", "")
        except Exception:
            return "History explanation failed"

    def show(self, explanation: Explanation) -> None:
        """Display explanation with Rich formatting."""
        body = Text()
        body.append(f"  {explanation.summary}\n\n", style="bold")
        body.append(explanation.detailed[:2000], style="white")
        if explanation.key_concepts:
            body.append("\n\n  Key Concepts: ", style="bold")
            body.append(", ".join(explanation.key_concepts), style="cyan")
        if explanation.diagram:
            body.append(f"\n\n{explanation.diagram}", style="dim")

        self.console.print(
            Panel(body, title=" 💡 Explanation ", border_style="yellow", padding=(0, 1))
        )

    def _extract_concepts(self, text: str) -> list[str]:
        keywords = [
            "recursion",
            "async",
            "generator",
            "decorator",
            "closure",
            "inheritance",
            "polymorphism",
            "memoization",
            "caching",
            "middleware",
            "ORM",
            "REST",
            "dependency injection",
            "factory pattern",
            "observer pattern",
            "singleton",
        ]
        return [k for k in keywords if k.lower() in text.lower()][:5]
