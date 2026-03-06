#!/usr/bin/env python3
"""
NexCode — AI-Powered Coding Assistant
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Entry point for the NexCode CLI application.
Loads configuration, initializes the display system, and bootstraps
the main application loop.

Usage:
    python main.py
    uv run python main.py
"""

from __future__ import annotations

import sys


def main() -> None:
    """Bootstrap and launch NexCode."""
    try:
        from nexcode.app import NexCodeApp
        from nexcode.config import load_config

        # Load configuration from .nexcode.toml files.
        config = load_config()

        # Initialize the application.
        app = NexCodeApp(config=config)

        # Run the interactive loop (startup + REPL + shutdown).
        app.run()

    except KeyboardInterrupt:
        print("\n  Interrupted. Goodbye! 👋")
        sys.exit(0)
    except Exception as exc:
        print(f"\n  ✗ Fatal error during startup: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
