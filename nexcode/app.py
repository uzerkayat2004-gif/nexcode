"""
NexCode App Orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~

Central application class that wires together configuration, display,
conversation history, AI providers, and the tool system.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from nexcode import __version__
from nexcode.ai.auth import AuthManager
from nexcode.ai.provider import AIProvider
from nexcode.commands.registry import CommandRegistry
from nexcode.config import NexCodeConfig, load_config
from nexcode.display import Display
from nexcode.history import ConversationHistory
from nexcode.tools.registry import ToolRegistry


class NexCodeApp:
    """
    Main application orchestrator for NexCode.

    Composes all subsystems and provides the primary run loop
    (to be fully implemented in later parts).
    """

    def __init__(self, config: NexCodeConfig | None = None) -> None:
        self.config = config or load_config()
        self.display = Display(theme=self.config.theme)
        self.history = ConversationHistory()
        self.workspace_root = Path.cwd()

        # Initialize auth manager with config-level API keys.
        self.auth = AuthManager(api_keys=dict(self.config.api_keys))

        # Initialize AI provider engine.
        self.provider = AIProvider(config=self.config, auth=self.auth)

        # Slash command registry.
        self.commands = CommandRegistry()
        self.commands.register_all()

        # Initialize the global tool registry.
        self._tool_registry = ToolRegistry()
        self._tool_registry.register_all()

        # Session Manager.
        from nexcode.memory.session import SessionManager
        self._session_manager = SessionManager(self.display.console)
        self.current_session = self._session_manager.start(
            project_path=str(self.workspace_root),
            model=self.provider.current_model,
            provider=self.provider.current_provider,
        )

    # -- Lifecycle -----------------------------------------------------------

    def startup(self) -> None:
        """Initialize the application and display the welcome screen."""
        self.display.show_banner()

        # Load workspace instructions if present.
        workspace_file = self.workspace_root / self.config.workspace_file
        if workspace_file.is_file():
            self.display.system(
                f"Loaded workspace instructions from {self.config.workspace_file}"
            )

        self.display.show_ready(
            model=self.provider.current_model,
            provider=self.provider.current_provider,
        )

    def shutdown(self) -> None:
        """Graceful shutdown — save session if configured."""
        if self.config.auto_save_session and hasattr(self, "current_session"):
            asyncio.run(self._session_manager.end(self.current_session, ai_provider=self.provider))
            self.display.system("Session saved.")
        self.display.system("Goodbye! 👋")

    # -- Interactive loop ----------------------------------------------------

    def run(self) -> None:
        """Launch the app: show banner then enter the interactive loop."""
        self.startup()
        try:
            asyncio.run(self._loop())
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    async def _loop(self) -> None:
        """Async REPL — read, eval, print, loop."""
        while True:
            try:
                user_input = await asyncio.to_thread(
                    input, "  \033[96mnexcode\033[0m › "
                )
            except (EOFError, KeyboardInterrupt):
                break

            text = user_input.strip()
            if not text:
                continue

            # Exit commands.
            if text.lower() in ("/exit", "/quit", "/q"):
                break

            # Slash commands.
            if self.commands.is_command(text):
                await self._handle_command(text)
                continue

            # Normal AI conversation.
            try:
                response = await self.process_input(text)
                self.display.print(response)
            except Exception as exc:
                self.display.error(f"Error: {exc}")

    async def _handle_command(self, text: str) -> None:
        """Route a slash command through the registry."""
        result = await self.commands.execute(
            text,
            auth_manager=self.auth,
            ai_provider=self.provider,
        )
        if result:
            if result.output:
                self.display.print(result.output)
            if not result.success and result.output:
                self.display.warning(result.output)

    # -- Conversation (stub) -------------------------------------------------

    async def process_input(self, user_input: str) -> str:
        """
        Process user input and run the agentic tool loop.
        """
        self.history.add_user(user_input)

        # Check context window usage.
        warning = self.provider.check_context_warnings(
            self.history.get_api_messages()
        )
        if warning:
            self.display.warning(warning)

        # Get API schemas for all enabled tools.
        tools = self._tool_registry.get_api_schemas()

        max_iterations = 10
        final_content = ""

        # The Agentic Loop: Think -> Act -> Observe.
        for _ in range(max_iterations):
            response = await self.provider.chat(
                messages=self.history.get_api_messages(),
                tools=tools,
            )

            # If the AI responded with text, log it.
            if response.content:
                self.history.add_assistant(response.content)
                self.display.print(response.format_footer())
                final_content = response.content

            # If there are no tool calls, the task is complete.
            if not response.tool_calls:
                break

            # The AI wants to execute tools.
            for call in response.tool_calls:
                # Add the tool call to history so the AI remembers it asked for this.
                self.history.add_tool_call(call.id, call.name, call.arguments)

                # Show the user what tool is running.
                self.display.tool_start(call.name, call.arguments)

                # Execute the tool safely safely.
                result = await self._tool_registry.execute(
                    tool_name=call.name,
                    parameters=call.arguments,
                )

                # Show the user the result.
                self.display.tool_end(call.name, result)

                # Add the tool result back to history for the AI's next turn.
                self.history.add_tool_result(call.id, result.output, not result.success)

        return final_content

    # -- Utilities -----------------------------------------------------------

    @property
    def version(self) -> str:
        """Return the current NexCode version."""
        return __version__

    def __repr__(self) -> str:
        return (
            f"NexCodeApp(model={self.provider.current_model!r}, "
            f"provider={self.provider.current_provider!r})"
        )
