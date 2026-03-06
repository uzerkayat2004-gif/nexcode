"""
NexCode Slash Command Registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Parses, routes, and executes slash commands.
Provides completions for the prompt engine.
"""

from __future__ import annotations

from typing import Any

from nexcode.commands.base import BaseCommand, CommandResult
from nexcode.commands.builtin import ALL_COMMANDS


class CommandRegistry:
    """
    Central registry for all slash commands.

    Handles parsing user input, routing to the correct command,
    executing it, and providing autocomplete suggestions.
    """

    def __init__(self) -> None:
        self._commands: dict[str, BaseCommand] = {}
        self._aliases: dict[str, str] = {}

    # ── Registration ───────────────────────────────────────────────────────

    def register(self, command: BaseCommand) -> None:
        """Register a single command."""
        self._commands[command.name] = command
        for alias in getattr(command, "aliases", []):
            self._aliases[alias] = command.name

    def register_all(self) -> None:
        """Register all built-in commands."""
        for cmd_cls in ALL_COMMANDS:
            self.register(cmd_cls())

    # ── Execution ──────────────────────────────────────────────────────────

    async def execute(
        self,
        input_text: str,
        context: Any = None,
        **services: Any,
    ) -> CommandResult | None:
        """
        Parse and execute a slash command.

        Returns None if input is not a slash command.
        """
        if not self.is_command(input_text):
            return None

        parts = input_text.lstrip("/").split()
        cmd_name = parts[0].lower()
        args = parts[1:]

        # Resolve aliases.
        if cmd_name in self._aliases:
            cmd_name = self._aliases[cmd_name]

        command = self._commands.get(cmd_name)
        if not command:
            return CommandResult(
                success=False,
                output=f"Unknown command: /{cmd_name}. Type /help for available commands.",
            )

        # Inject registry itself so /help can list commands.
        services["command_registry"] = self

        return await command.execute(args, context, **services)

    # ── Query ──────────────────────────────────────────────────────────────

    def is_command(self, text: str) -> bool:
        """Check if input starts with /."""
        return text.strip().startswith("/")

    def get(self, name: str) -> BaseCommand | None:
        """Get a command by name or alias."""
        if name.startswith("/"):
            name = name[1:]
        if name in self._commands:
            return self._commands[name]
        if name in self._aliases:
            return self._commands.get(self._aliases[name])
        return None

    def list_all(self) -> dict[str, list[BaseCommand]]:
        """List all commands grouped by category."""
        grouped: dict[str, list[BaseCommand]] = {}
        for cmd in self._commands.values():
            cat = cmd.category
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(cmd)
        return grouped

    def get_command_names(self) -> list[str]:
        """Get all command names prefixed with /."""
        names = [f"/{name}" for name in self._commands]
        names.extend(f"/{alias}" for alias in self._aliases)
        return sorted(names)

    def get_completions(self, partial: str) -> list[str]:
        """Get completions for partial command input."""
        if not partial.startswith("/"):
            return []
        prefix = partial[1:].lower()
        matches: list[str] = []
        for name in self._commands:
            if name.startswith(prefix):
                matches.append(f"/{name}")
        for alias in self._aliases:
            if alias.startswith(prefix):
                matches.append(f"/{alias}")
        return sorted(matches)

    @property
    def count(self) -> int:
        return len(self._commands)
