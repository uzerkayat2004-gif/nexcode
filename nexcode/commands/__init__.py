"""Slash command system for NexCode."""

from nexcode.commands.base import BaseCommand, CommandResult
from nexcode.commands.builtin import ALL_COMMANDS
from nexcode.commands.registry import CommandRegistry

__all__ = [
    "ALL_COMMANDS",
    "BaseCommand",
    "CommandRegistry",
    "CommandResult",
]
