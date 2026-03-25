"""
NexCode Input Prompt
~~~~~~~~~~~~~~~~~~~~~

Dynamic prompt with git branch, context bar, slash command
autocomplete, multi-line editing, and persistent history.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HISTORY_FILE = Path.home() / ".nexcode" / "history"


# ---------------------------------------------------------------------------
# NexCodePrompt
# ---------------------------------------------------------------------------

class NexCodePrompt:
    """
    Dynamic terminal prompt with git branch, context usage bar,
    slash command autocomplete, multi-line input, and history.
    """

    def __init__(
        self,
        context: Any = None,
        git_engine: Any = None,
        theme: Any = None,
        console: Console | None = None,
        commands: list[str] | None = None,
    ) -> None:
        self.context = context
        self.git_engine = git_engine
        self.theme = theme
        self.console = console or Console()
        self._commands = commands or []
        self._history: list[str] = []
        self._load_history()

    # ── Main input ─────────────────────────────────────────────────────────

    async def get_input(self) -> str:
        """Get input from user with the dynamic prompt."""
        prompt_str = self._build_prompt_string()

        try:
            # Try prompt_toolkit for rich input.
            return await self._get_input_prompt_toolkit(prompt_str)
        except ImportError:
            # Fallback to basic input.
            return self._get_input_basic(prompt_str)

    def _get_input_basic(self, prompt_str: str) -> str:
        """Basic input fallback when prompt_toolkit unavailable."""
        self.console.print(prompt_str, end="")
        try:
            line = input("")
            # Multi-line: if line ends with \, continue reading.
            lines = [line]
            while line.endswith("\\"):
                lines[-1] = lines[-1][:-1]
                self.console.print("       · ", end="", style="dim")
                line = input("")
                lines.append(line)
            result = "\n".join(lines).strip()
            if result:
                self._add_history(result)
            return result
        except EOFError:
            return "/exit"
        except KeyboardInterrupt:
            return ""

    async def _get_input_prompt_toolkit(self, prompt_display: str) -> str:
        """Rich input using prompt_toolkit."""
        import asyncio

        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.key_binding import KeyBindings

        # Build completions list.
        completions = list(self._commands)

        completer = WordCompleter(completions, sentence=True)

        # Key bindings.
        bindings = KeyBindings()

        @bindings.add("escape", "enter")
        def _newline(event: Any) -> None:
            event.current_buffer.insert_text("\n")

        # Ensure history dir exists.
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        session: PromptSession[str] = PromptSession(
            history=FileHistory(str(_HISTORY_FILE)),
            completer=completer,
            key_bindings=bindings,
            multiline=False,
            enable_history_search=True,
        )

        # Use plain string prompt for prompt_toolkit.
        plain_prompt = self._build_plain_prompt()

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: session.prompt(plain_prompt)
            )
            return result.strip()
        except EOFError:
            return "/exit"
        except KeyboardInterrupt:
            return ""

    # ── Prompt building ────────────────────────────────────────────────────

    def _build_prompt_string(self) -> str:
        """Build a Rich-formatted prompt string."""
        parts: list[str] = []
        parts.append("[bold cyan]nexcode[/]")

        # Git branch.
        branch_info = self._get_git_info()
        if branch_info:
            parts.append(f" [dim]on[/] {branch_info}")

        # Context usage.
        if self.context:
            usage = self.context.get_usage_display()
            color = self.context.get_usage_color()
            parts.append(f" [{color}]{usage}[/]")

        parts.append(" [bold cyan]›[/] ")
        return "".join(parts)

    def _build_plain_prompt(self) -> str:
        """Build a plain text prompt for prompt_toolkit."""
        parts = ["nexcode"]

        branch = self._get_branch_name()
        if branch:
            parts.append(f" on 🌿 {branch}")

        if self.context:
            pct = self.context.get_usage_percent()
            parts.append(f" [{pct:.0f}%]")

        parts.append(" › ")
        return "".join(parts)

    def _get_git_info(self) -> str:
        """Get git branch info with status indicators."""
        if not self.git_engine:
            return ""
        try:
            if not self.git_engine.is_git_repo():
                return ""
            status = self.git_engine.get_status()
            color = "green"
            if status.has_conflicts:
                color = "red"
            elif status.is_dirty:
                color = "yellow"

            info = f"[{color}]🌿 {status.branch}[/]"
            if status.ahead_commits > 0:
                info += f" [cyan]↑{status.ahead_commits}[/]"
            if status.behind_commits > 0:
                info += f" [yellow]↓{status.behind_commits}[/]"
            return info
        except Exception:
            return ""

    def _get_branch_name(self) -> str:
        """Get just the branch name (plaintext)."""
        if not self.git_engine:
            return ""
        try:
            if self.git_engine.is_git_repo():
                return self.git_engine.get_current_branch()
        except Exception:
            pass
        return ""

    # ── History ────────────────────────────────────────────────────────────

    def _add_history(self, text: str) -> None:
        self._history.append(text)
        try:
            _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass

    def _load_history(self) -> None:
        if _HISTORY_FILE.exists():
            try:
                lines = _HISTORY_FILE.read_text(encoding="utf-8").strip().splitlines()
                self._history = lines[-500:]
            except OSError:
                pass

    def refresh(self) -> None:
        """Refresh prompt data (git, context)."""
        pass  # Data is fetched live on each prompt build.

    def set_commands(self, commands: list[str]) -> None:
        """Update the list of available slash commands for autocomplete."""
        self._commands = commands
