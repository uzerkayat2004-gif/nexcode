"""
NexCode Base Command
~~~~~~~~~~~~~~~~~~~~~

Base class for all slash commands and the CommandResult dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommandResult:
    """Result of executing a slash command."""

    success: bool
    output: str | None = None
    clear_screen: bool = False
    exit_app: bool = False


class BaseCommand:
    """
    Base class for all NexCode slash commands.

    Subclass and override ``execute`` to implement a command.
    """

    name: str = ""
    aliases: list[str] = []
    description: str = ""
    usage: str = ""
    category: str = "system"  # session, model, auth, safety, tools, git, system

    async def execute(self, args: list[str], context: Any = None, **services: Any) -> CommandResult:
        """Execute the command.  Override in subclasses."""
        return CommandResult(success=False, output="Not implemented")

    def get_completions(self, partial: str) -> list[str]:
        """Return tab-completions for this command's arguments."""
        return []
