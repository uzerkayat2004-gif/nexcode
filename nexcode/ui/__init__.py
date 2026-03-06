"""Terminal UI system for NexCode."""

from nexcode.ui.prompt import NexCodePrompt
from nexcode.ui.renderer import OutputRenderer
from nexcode.ui.status_bar import StatusBar
from nexcode.ui.terminal import NexCodeTerminal
from nexcode.ui.themes import THEMES, Theme, ThemeManager

__all__ = [
    "NexCodePrompt",
    "NexCodeTerminal",
    "OutputRenderer",
    "StatusBar",
    "THEMES",
    "Theme",
    "ThemeManager",
]
