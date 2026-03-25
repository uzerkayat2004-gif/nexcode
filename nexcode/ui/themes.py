"""
NexCode Theme System
~~~~~~~~~~~~~~~~~~~~~

Complete theming with 6 built-in themes and a manager
for switching at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


@dataclass
class Theme:
    """Full color theme definition."""

    name: str

    # Core
    primary: str
    secondary: str
    success: str
    warning: str
    error: str
    info: str
    dim: str

    # Messages
    user_message: str
    ai_message: str
    tool_call: str
    tool_result: str
    system: str
    prompt: str

    # Panels
    panel_border: str
    panel_title: str

    # Code
    code_theme: str  # Rich Syntax theme name


# ---------------------------------------------------------------------------
# Built-in themes
# ---------------------------------------------------------------------------

THEMES: dict[str, Theme] = {
    "dark": Theme(
        name="dark",
        primary="cyan", secondary="blue",
        success="green", warning="yellow", error="red",
        info="blue", dim="grey50",
        user_message="bold white", ai_message="bright_white",
        tool_call="yellow", tool_result="green",
        system="grey70", prompt="bold cyan",
        panel_border="cyan", panel_title="bold cyan",
        code_theme="monokai",
    ),
    "light": Theme(
        name="light",
        primary="blue", secondary="dark_blue",
        success="green", warning="dark_orange", error="red",
        info="blue", dim="grey62",
        user_message="bold black", ai_message="black",
        tool_call="dark_orange", tool_result="dark_green",
        system="grey50", prompt="bold blue",
        panel_border="blue", panel_title="bold blue",
        code_theme="github-dark",
    ),
    "dracula": Theme(
        name="dracula",
        primary="medium_purple1", secondary="deep_pink2",
        success="green1", warning="dark_orange",
        error="red1", info="dodger_blue2", dim="grey50",
        user_message="bold white", ai_message="grey89",
        tool_call="medium_purple1", tool_result="green1",
        system="grey62", prompt="bold medium_purple1",
        panel_border="medium_purple1", panel_title="bold deep_pink2",
        code_theme="dracula",
    ),
    "nord": Theme(
        name="nord",
        primary="steel_blue1", secondary="sky_blue3",
        success="dark_sea_green2", warning="light_goldenrod1",
        error="indian_red1", info="steel_blue1", dim="grey50",
        user_message="bold white", ai_message="grey89",
        tool_call="sky_blue3", tool_result="dark_sea_green2",
        system="grey62", prompt="bold steel_blue1",
        panel_border="steel_blue1", panel_title="bold steel_blue1",
        code_theme="nord",
    ),
    "tokyo": Theme(
        name="tokyo",
        primary="medium_purple1", secondary="dodger_blue1",
        success="spring_green2", warning="light_goldenrod1",
        error="indian_red1", info="dodger_blue1", dim="grey42",
        user_message="bold white", ai_message="grey89",
        tool_call="dodger_blue1", tool_result="spring_green2",
        system="grey58", prompt="bold medium_purple1",
        panel_border="medium_purple1", panel_title="bold dodger_blue1",
        code_theme="monokai",
    ),
    "minimal": Theme(
        name="minimal",
        primary="white", secondary="grey74",
        success="white", warning="white", error="white",
        info="white", dim="grey42",
        user_message="bold white", ai_message="white",
        tool_call="grey74", tool_result="white",
        system="grey58", prompt="bold white",
        panel_border="grey50", panel_title="bold white",
        code_theme="monokai",
    ),
}


# ---------------------------------------------------------------------------
# ThemeManager
# ---------------------------------------------------------------------------

class ThemeManager:
    """Manages theme selection and switching."""

    def __init__(self, default: str = "dark") -> None:
        self._current = THEMES.get(default, THEMES["dark"])

    @property
    def current(self) -> Theme:
        return self._current

    def get(self, name: str) -> Theme:
        return THEMES.get(name, self._current)

    def set(self, name: str) -> bool:
        if name in THEMES:
            self._current = THEMES[name]
            return True
        return False

    def list_themes(self, console: Console | None = None) -> None:
        """Show all themes with colored previews."""
        console = console or Console()
        for name, theme in THEMES.items():
            marker = " ◀ active" if name == self._current.name else ""
            text = Text()
            text.append(f"  {name:<10}", style=f"bold {theme.primary}")
            text.append(" │ ", style="dim")
            text.append("primary ", style=theme.primary)
            text.append("success ", style=theme.success)
            text.append("warning ", style=theme.warning)
            text.append("error", style=theme.error)
            if marker:
                text.append(marker, style="bold green")
            console.print(text)

    def preview(self, name: str, console: Console | None = None) -> None:
        """Show a mini preview of a theme."""
        console = console or Console()
        theme = THEMES.get(name)
        if not theme:
            console.print(f"  [red]Unknown theme: {name}[/]")
            return

        body = Text()
        body.append(f"  Theme: {theme.name}\n\n", style=f"bold {theme.primary}")
        body.append("  User message\n", style=theme.user_message)
        body.append("  AI response text\n", style=theme.ai_message)
        body.append("  🔧 Tool call\n", style=theme.tool_call)
        body.append("  ✅ Tool result\n", style=theme.tool_result)
        body.append("  System info\n", style=theme.system)
        body.append("  Dim text\n", style=theme.dim)

        console.print(Panel(
            body, border_style=theme.panel_border,
            title=f" {theme.name} ", title_align="left",
        ))
