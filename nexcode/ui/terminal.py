"""
NexCode Terminal — Main Interactive Loop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Wires everything together: banner, auth, prompt,
slash commands, agent loop, and graceful shutdown.
"""

from __future__ import annotations

import os
from typing import Any

from rich.console import Console
from rich.text import Text

from nexcode.commands.registry import CommandRegistry
from nexcode.ui.prompt import NexCodePrompt
from nexcode.ui.renderer import OutputRenderer
from nexcode.ui.status_bar import StatusBar
from nexcode.ui.themes import ThemeManager

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

BANNER = r"""
  [bold cyan]███╗   ██╗███████╗██╗  ██╗ ██████╗ ██████╗ ██████╗ ███████╗[/]
  [bold cyan]████╗  ██║██╔════╝╚██╗██╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝[/]
  [bold cyan]██╔██╗ ██║█████╗   ╚███╔╝ ██║     ██║   ██║██║  ██║█████╗  [/]
  [bold cyan]██║╚██╗██║██╔══╝   ██╔██╗ ██║     ██║   ██║██║  ██║██╔══╝  [/]
  [bold cyan]██║ ╚████║███████╗██╔╝ ██╗╚██████╗╚██████╔╝██████╔╝███████╗[/]
  [bold cyan]╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝[/]
"""


# ---------------------------------------------------------------------------
# NexCodeTerminal
# ---------------------------------------------------------------------------

class NexCodeTerminal:
    """
    Main interactive terminal loop.

    Orchestrates the prompt, slash commands, agent loop,
    and all UI rendering.
    """

    def __init__(
        self,
        config: Any = None,
        ai_provider: Any = None,
        tool_registry: Any = None,
        guardian: Any = None,
        console: Console | None = None,
    ) -> None:
        self.config = config
        self.ai_provider = ai_provider
        self.tool_registry = tool_registry
        self.guardian = guardian
        self.console = console or Console()

        # UI components.
        self.theme_manager = ThemeManager()
        self.renderer = OutputRenderer(self.theme_manager.current, self.console)
        self.status_bar = StatusBar(self.theme_manager.current, self.console)

        # Commands.
        self.commands = CommandRegistry()
        self.commands.register_all()

        # Context & prompt.
        from nexcode.agent.context import AgentContext
        self.context = AgentContext()

        self.prompt = NexCodePrompt(
            context=self.context,
            console=self.console,
            commands=self.commands.get_command_names(),
        )

        # Session & memory.
        self._session: Any = None
        self._session_manager: Any = None
        self._long_term_memory: Any = None
        self._project_manager: Any = None
        self._running = False

    # ── Main entry point ───────────────────────────────────────────────────

    async def run(self) -> None:
        """Start the interactive terminal loop."""
        self._running = True

        # Show banner.
        self._show_banner()

        # Initialize services.
        self._init_services()

        # Main loop.
        while self._running:
            try:
                user_input = await self.prompt.get_input()

                if not user_input.strip():
                    continue

                await self.process_turn(user_input)

            except KeyboardInterrupt:
                self.console.print("\n  [dim]Type /exit to quit or press Enter to continue[/]")
                continue
            except EOFError:
                await self.shutdown()
                break

    # ── Process a single turn ──────────────────────────────────────────────

    async def process_turn(self, user_input: str) -> None:
        """Process one turn: slash command or AI task."""
        stripped = user_input.strip()

        # Slash command?
        if self.commands.is_command(stripped):
            await self.handle_command(stripped)
            return

        # AI task.
        await self.handle_task(stripped)

    # ── Slash command handler ──────────────────────────────────────────────

    async def handle_command(self, input_text: str) -> bool:
        """Handle a slash command. Returns True if handled."""
        result = await self.commands.execute(
            input_text,
            context=self.context,
            console=self.console,
            config=self.config,
            ai_provider=self.ai_provider,
            tool_registry=self.tool_registry,
            guardian=self.guardian,
            session=self._session,
            session_manager=self._session_manager,
            long_term_memory=self._long_term_memory,
            project_manager=self._project_manager,
            theme_manager=self.theme_manager,
        )

        if result is None:
            return False

        if result.clear_screen:
            self.console.clear()

        if result.output:
            self.renderer.render_system(result.output, "success" if result.success else "error")

        if result.exit_app:
            await self.shutdown()

        return True

    # ── AI task handler ────────────────────────────────────────────────────

    async def handle_task(self, instruction: str) -> None:
        """Run an instruction through the agent loop."""
        self.renderer.render_user_message(instruction)

        if not self.ai_provider:
            self.renderer.render_system(
                "No AI provider configured. Run /auth to set up authentication.",
                "error",
            )
            return

        if not self.tool_registry:
            self.renderer.render_system("Tool registry not initialized.", "error")
            return

        try:
            from nexcode.agent.loop import AgentLoop

            loop = AgentLoop(
                ai_provider=self.ai_provider,
                tool_registry=self.tool_registry,
                context=self.context,
                console=self.console,
            )

            task = await loop.run(instruction)

            # Update session stats.
            if self._session:
                self._session.tasks_completed += 1
                self._session.tools_called += len(task.tools_used)
                self._session.files_modified.extend(task.files_modified)

            # Response footer.
            self.renderer.render_footer(
                model=getattr(self.ai_provider, "model", ""),
                provider=getattr(self.ai_provider, "provider", ""),
            )

        except Exception as exc:
            self.renderer.render_system(f"Agent error: {exc}", "error")

    # ── Shutdown ───────────────────────────────────────────────────────────

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        self._running = False

        # End session.
        if self._session and self._session_manager:
            try:
                await self._session_manager.end(self._session, self.ai_provider)
            except Exception:
                pass

        # Save context.
        try:
            self.context.save()
        except Exception:
            pass

    # ── Services init ──────────────────────────────────────────────────────

    def _init_services(self) -> None:
        """Initialize memory and session services."""
        try:
            from nexcode.memory.long_term import LongTermMemory
            from nexcode.memory.project import ProjectMemoryManager
            from nexcode.memory.session import SessionManager
            from nexcode.memory.store import MemoryStore

            store = MemoryStore()
            self._session_manager = SessionManager(self.console)
            self._long_term_memory = LongTermMemory(store)
            self._project_manager = ProjectMemoryManager(store)

            # Start session.
            model = getattr(self.ai_provider, "model", "") if self.ai_provider else ""
            provider = getattr(self.ai_provider, "provider", "") if self.ai_provider else ""
            self._session = self._session_manager.start(os.getcwd(), model, provider)
        except Exception:
            pass

        # Try to attach git engine to prompt.
        try:
            from nexcode.git.engine import GitEngine
            engine = GitEngine()
            if engine.is_git_repo():
                self.prompt.git_engine = engine
        except Exception:
            pass

    # ── Banner ─────────────────────────────────────────────────────────────

    def _show_banner(self) -> None:
        """Show the startup banner."""
        self.console.print(BANNER)

        model = getattr(self.ai_provider, "model", "not configured") if self.ai_provider else "not configured"
        provider = getattr(self.ai_provider, "provider", "—") if self.ai_provider else "—"
        mode = "ask"
        if self.guardian:
            mode = self.guardian.permissions.mode
        project = os.path.basename(os.getcwd())

        info = Text()
        info.append("  v1.0.0", style="dim")
        info.append("  │  ", style="dim")
        info.append("Better than Claude Code", style="dim")
        info.append("  │  ", style="dim")
        info.append("Type /help to start\n\n", style="dim")
        info.append(f"  Model:    {model} ({provider})\n", style="white")
        info.append(f"  Mode:     {mode}\n", style="white")
        info.append(f"  Project:  {project}\n", style="white")

        self.console.print(info)
        self.console.print("─" * 60, style="bright_black")
        self.console.print()
