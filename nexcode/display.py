"""
NexCode Display System
~~~~~~~~~~~~~~~~~~~~~~~

Rich-powered terminal UI with color-coded messages, ASCII banner,
spinners, and clean formatting for a premium CLI experience.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.text import Text
from rich.theme import Theme

from nexcode import __app_name__, __version__


# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------

DARK_THEME = Theme({
    "user": "bold dodger_blue2",
    "ai": "bold green",
    "tool": "bold yellow",
    "error": "bold red",
    "system": "dim white",
    "info": "cyan",
    "accent": "magenta",
    "muted": "bright_black",
})

LIGHT_THEME = Theme({
    "user": "bold blue",
    "ai": "bold dark_green",
    "tool": "bold dark_orange",
    "error": "bold red",
    "system": "dim black",
    "info": "dark_cyan",
    "accent": "dark_magenta",
    "muted": "bright_black",
})


# ---------------------------------------------------------------------------
# ASCII Art Banner
# ---------------------------------------------------------------------------

BANNER_ART = r"""
[bold cyan]  ███╗   ██╗███████╗██╗  ██╗ ██████╗ ██████╗ ██████╗ ███████╗[/]
[bold cyan]  ████╗  ██║██╔════╝╚██╗██╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝[/]
[bold cyan]  ██╔██╗ ██║█████╗   ╚███╔╝ ██║     ██║   ██║██║  ██║█████╗  [/]
[bold cyan]  ██║╚██╗██║██╔══╝   ██╔██╗ ██║     ██║   ██║██║  ██║██╔══╝  [/]
[bold cyan]  ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╗╚██████╔╝██████╔╝███████╗[/]
[bold cyan]  ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝[/]
"""


# ---------------------------------------------------------------------------
# Display class
# ---------------------------------------------------------------------------

class Display:
    """
    Rich-based terminal display manager for NexCode.

    Provides color-coded message rendering, ASCII art banners, spinners,
    and clean visual separation between conversation turns.
    """

    def __init__(self, theme: str = "dark") -> None:
        rich_theme = DARK_THEME if theme == "dark" else LIGHT_THEME
        self.console = Console(theme=rich_theme, highlight=False)
        self.theme_name = theme

    # -- Banner & startup ----------------------------------------------------

    def show_banner(self) -> None:
        """Display the NexCode ASCII art banner with version info."""
        self.console.print(BANNER_ART)
        self.console.print(
            Text.assemble(
                ("  ⚡ ", "bold yellow"),
                (f"{__app_name__} ", "bold white"),
                (f"v{__version__}", "muted"),
                ("  —  ", "muted"),
                ("AI-Powered Coding Assistant", "info"),
            )
        )
        self.console.print()

    def show_ready(self, model: str, provider: str) -> None:
        """Display the 'Ready.' status with current model info."""
        self.console.print(
            Panel(
                Text.assemble(
                    ("✓ Ready", "bold green"),
                    ("  •  ", "muted"),
                    ("Model: ", "system"),
                    (model, "bold white"),
                    ("  •  ", "muted"),
                    ("Provider: ", "system"),
                    (provider, "bold white"),
                ),
                border_style="green",
                padding=(0, 2),
            )
        )
        self.console.print()

    # -- Message rendering ---------------------------------------------------

    def user_message(self, text: str) -> None:
        """Render a user input message."""
        self.console.print(
            Panel(
                Text(text),
                title="[user]  You[/user]",
                title_align="left",
                border_style="dodger_blue2",
                padding=(0, 2),
            )
        )

    def ai_message(self, text: str) -> None:
        """Render an AI response message as Markdown."""
        md = Markdown(text)
        self.console.print(
            Panel(
                md,
                title="[ai]🤖 NexCode[/ai]",
                title_align="left",
                border_style="green",
                padding=(0, 2),
            )
        )

    def tool_message(self, tool_name: str, detail: str = "") -> None:
        """Render a tool call notification."""
        body = Text.assemble(
            ("⚙ ", "bold yellow"),
            (tool_name, "bold white"),
        )
        if detail:
            body.append(f"  {detail}", style="muted")

        self.console.print(
            Panel(
                body,
                title="[tool]🔧 Tool Call[/tool]",
                title_align="left",
                border_style="yellow",
                padding=(0, 2),
            )
        )

    def tool_start(self, tool_name: str, arguments: dict | None = None) -> None:
        """Show that a tool is about to execute."""
        body = Text.assemble(
            ("⚙ Running ", "bold yellow"),
            (tool_name, "bold white"),
        )
        if arguments:
            # Show a compact one-line summary of the arguments.
            import json
            compact = json.dumps(arguments, ensure_ascii=False)
            if len(compact) > 120:
                compact = compact[:117] + "..."
            body.append(f"\n  {compact}", style="muted")

        self.console.print(
            Panel(
                body,
                title="[tool]🔧 Tool Call[/tool]",
                title_align="left",
                border_style="yellow",
                padding=(0, 2),
            )
        )

    def tool_end(self, tool_name: str, result: object) -> None:
        """Show the result of a tool execution."""
        # result is expected to be a ToolResult with .success, .display, .error
        success = getattr(result, "success", True)
        display_text = getattr(result, "display", "") or getattr(result, "output", "")
        error_text = getattr(result, "error", None)

        if success:
            body = Text.assemble(
                ("✓ ", "bold green"),
                (tool_name, "bold white"),
                (" completed", "green"),
            )
            if display_text:
                # Truncate very long output for the terminal.
                shown = display_text if len(display_text) <= 500 else display_text[:497] + "..."
                body.append(f"\n{shown}", style="dim white")
            self.console.print(
                Panel(
                    body,
                    title="[green]✓ Tool Result[/green]",
                    title_align="left",
                    border_style="green",
                    padding=(0, 2),
                )
            )
        else:
            body = Text.assemble(
                ("✗ ", "bold red"),
                (tool_name, "bold white"),
                (" failed", "red"),
            )
            if error_text:
                body.append(f"\n{error_text}", style="red")
            self.console.print(
                Panel(
                    body,
                    title="[red]✗ Tool Error[/red]",
                    title_align="left",
                    border_style="red",
                    padding=(0, 2),
                )
            )

    def error(self, message: str, *, title: str = "Error") -> None:
        """Render an error message."""
        self.console.print(
            Panel(
                Text(message, style="error"),
                title=f"[error]✗ {title}[/error]",
                title_align="left",
                border_style="red",
                padding=(0, 2),
            )
        )

    def system(self, message: str) -> None:
        """Render a system / informational message."""
        self.console.print(Text(f"  ℹ {message}", style="system"))

    def warning(self, message: str) -> None:
        """Render a warning message."""
        self.console.print(Text(f"  ⚠ {message}", style="bold yellow"))

    # -- Visual elements -----------------------------------------------------

    def separator(self) -> None:
        """Print a clean separator rule between conversation turns."""
        self.console.print(Rule(style="bright_black"))

    @contextmanager
    def spinner(self, message: str = "Thinking…") -> Generator[Live, None, None]:
        """
        Context manager showing an animated spinner while AI is processing.

        Usage::

            with display.spinner("Analyzing code..."):
                result = await ai.generate(...)
        """
        spinner_widget = Spinner("dots", text=Text(f" {message}", style="info"))
        with Live(spinner_widget, console=self.console, transient=True) as live:
            yield live

    def print(self, *args: object, **kwargs: object) -> None:
        """Passthrough to the underlying Rich console."""
        self.console.print(*args, **kwargs)  # type: ignore[arg-type]
