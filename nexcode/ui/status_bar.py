"""
NexCode Status Bar
~~~~~~~~~~~~~~~~~~~

Persistent status line at the bottom of the terminal
showing model, mode, context usage, and session cost.
"""

from __future__ import annotations

from rich.console import Console

from nexcode.ui.themes import THEMES, Theme


class StatusBar:
    """
    Bottom status bar with model, mode, context %, and cost.
    """

    def __init__(self, theme: Theme | None = None, console: Console | None = None) -> None:
        self.theme = theme or THEMES["dark"]
        self.console = console or Console()
        self._visible = True
        self._model = ""
        self._provider = ""
        self._mode = "ask"
        self._context_pct = 0.0
        self._cost = 0.0
        self._task_running = False

    def update(
        self,
        model: str = "",
        provider: str = "",
        mode: str = "",
        context_pct: float = 0.0,
        session_cost: float = 0.0,
        task_running: bool = False,
    ) -> None:
        """Update status bar values."""
        if model:
            self._model = model
        if provider:
            self._provider = provider
        if mode:
            self._mode = mode
        self._context_pct = context_pct
        self._cost = session_cost
        self._task_running = task_running

    def render(self) -> None:
        """Render the status bar."""
        if not self._visible:
            return

        parts: list[str] = []
        parts.append(f"[bold {self.theme.primary}] NexCode v1.0 [/]")
        parts.append(f"[{self.theme.dim}]│[/]")

        if self._model:
            parts.append(f"  [{self.theme.ai_message}]{self._model}[/]")
            parts.append(f"  [{self.theme.dim}]│[/]")

        # Mode with color.
        mode_colors = {"ask": "cyan", "auto": "green", "strict": "yellow", "yolo": "red"}
        mc = mode_colors.get(self._mode, "white")
        parts.append(f"  [{mc}]{self._mode} mode[/]")
        parts.append(f"  [{self.theme.dim}]│[/]")

        # Context %.
        ctx_color = "green"
        if self._context_pct > 80:
            ctx_color = "red"
        elif self._context_pct > 60:
            ctx_color = "yellow"
        parts.append(f"  [{ctx_color}]ctx: {self._context_pct:.0f}%[/]")
        parts.append(f"  [{self.theme.dim}]│[/]")

        # Cost.
        parts.append(f"  [{self.theme.dim}]cost: ${self._cost:.4f}[/]")
        parts.append(f"  [{self.theme.dim}]│[/]")

        parts.append(f"  [{self.theme.dim}]F1 help[/]")

        self.console.print("".join(parts))

    def show(self) -> None:
        self._visible = True

    def hide(self) -> None:
        self._visible = False
