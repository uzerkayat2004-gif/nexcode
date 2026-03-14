"""
NexCode Output Renderer
~~~~~~~~~~~~~~~~~~~~~~~~

Beautiful rendering for AI responses (markdown, code blocks),
tool calls, tool results, system messages, and response footers.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from nexcode.ui.themes import Theme, THEMES
from nexcode.utils.helpers import truncate


class OutputRenderer:
    """
    Premium terminal output renderer.

    Handles AI markdown, syntax-highlighted code, tool call
    panels, result summaries, system messages, and footers.
    """

    def __init__(self, theme: Theme | None = None, console: Console | None = None) -> None:
        self.theme = theme or THEMES["dark"]
        self.console = console or Console()

    # ── User message ───────────────────────────────────────────────────────

    def render_user_message(self, text: str) -> None:
        """Echo back the user's input."""
        self.console.print(f"\n  [dim]You:[/] [{self.theme.user_message}]{text}[/]\n")

    # ── AI response ────────────────────────────────────────────────────────

    def render_ai_response(self, text: str, stream: bool = False) -> None:
        """Render AI response with full markdown support."""
        if not text.strip():
            return

        self.console.print()
        self.console.print(Panel(
            Markdown(text),
            title=" NexCode ",
            title_align="left",
            border_style=self.theme.panel_border,
            padding=(1, 2),
        ))
        self.console.print()

    # ── Tool call ──────────────────────────────────────────────────────────

    def render_tool_call(self, tool_name: str, parameters: dict[str, Any], step: int) -> None:
        """Render a tool being called."""
        body = Text()
        body.append(f"🔧 {tool_name}\n", style=f"bold {self.theme.tool_call}")

        for key, value in parameters.items():
            display = truncate(str(value), 200, suffix="...")
            body.append(f"   {key}:", style="dim")
            body.append(f'  "{display}"\n', style="white")

        self.console.print(Panel(
            body, border_style=self.theme.tool_call,
            padding=(0, 1), expand=False,
        ))

    # ── Tool result ────────────────────────────────────────────────────────

    def render_tool_result(self, tool_name: str, result: Any, duration_ms: int = 0) -> None:
        """Render a tool's result."""
        success = getattr(result, "success", True)
        display = str(getattr(result, "display", getattr(result, "output", result)))
        error = getattr(result, "error", None)

        icon = "✅" if success else "❌"
        color = self.theme.success if success else self.theme.error
        time_str = f" ({duration_ms}ms)" if duration_ms else ""

        text = Text()
        text.append(f" {icon} {tool_name} completed{time_str}\n", style=color)

        # Show brief output.
        if display and len(display) < 200:
            text.append(f"    {display}\n", style="dim")
        if error:
            text.append(f"    Error: {error}\n", style=self.theme.error)

        self.console.print(text)

    # ── Step separator ─────────────────────────────────────────────────────

    def render_step(self, step: int, max_steps: int) -> None:
        """Render the step counter."""
        self.console.print(Rule(
            f" Step {step} / {max_steps} ",
            style="bright_black",
        ))

    def render_separator(self) -> None:
        """Render a visual separator between turns."""
        self.console.print(Rule(style="bright_black"))

    # ── System message ─────────────────────────────────────────────────────

    def render_system(self, message: str, level: str = "info") -> None:
        """Render a system message."""
        icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅"}
        colors = {
            "info": self.theme.info,
            "warning": self.theme.warning,
            "error": self.theme.error,
            "success": self.theme.success,
        }
        icon = icons.get(level, "ℹ️")
        color = colors.get(level, self.theme.system)
        self.console.print(f"  [{color}]{icon}  {message}[/]")

    # ── Response footer ────────────────────────────────────────────────────

    def render_footer(
        self,
        model: str = "",
        provider: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        duration_ms: int = 0,
    ) -> None:
        """Render the response footer with stats."""
        parts: list[str] = []
        if model:
            parts.append(model)
        if provider:
            parts.append(provider)
        total_tokens = input_tokens + output_tokens
        if total_tokens:
            parts.append(f"{total_tokens:,} tokens")
        if cost_usd > 0:
            parts.append(f"~${cost_usd:.4f}")
        if duration_ms:
            secs = duration_ms / 1000
            parts.append(f"{secs:.1f}s")

        if parts:
            footer = " · ".join(parts)
            self.console.print(f"\n  [{self.theme.dim}]{footer}[/]\n")

    # ── Code block ─────────────────────────────────────────────────────────

    def render_code(self, code: str, language: str = "python") -> None:
        """Render a syntax-highlighted code block."""
        syntax = Syntax(
            code, language,
            theme=self.theme.code_theme,
            line_numbers=True,
            padding=1,
        )
        self.console.print(Panel(
            syntax,
            title=f" {language} ",
            title_align="left",
            border_style=self.theme.dim,
            expand=True,
        ))

    # ── Markdown ───────────────────────────────────────────────────────────

    def render_markdown(self, text: str) -> None:
        """Render a markdown document."""
        self.console.print(Markdown(text))

    # ── Table ──────────────────────────────────────────────────────────────

    def render_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        title: str | None = None,
    ) -> None:
        """Render a data table."""
        table = Table(
            title=title, title_style="bold white",
            border_style="bright_black", show_lines=True,
        )
        for h in headers:
            table.add_column(h)
        for row in rows:
            table.add_row(*row)
        self.console.print()
        self.console.print(table)
        self.console.print()


