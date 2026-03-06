"""
NexCode Auto Changelog Generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generates changelogs from git history with AI
categorization and semver suggestion.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console


@dataclass
class ChangelogEntry:
    version: str = ""
    date: str = ""
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    security: list[str] = field(default_factory=list)
    breaking: list[str] = field(default_factory=list)


class ChangelogGenerator:
    """AI-powered changelog from git history."""

    def __init__(self, ai_provider: Any = None, console: Console | None = None) -> None:
        self.ai = ai_provider
        self.console = console or Console()

    async def generate(
        self,
        from_tag: str | None = None,
        to_tag: str | None = None,
        format: str = "keepachangelog",
    ) -> str:
        """Generate full changelog from git history."""
        commits = self._get_commits(from_tag, to_tag)
        if not commits:
            return "# Changelog\n\nNo commits found."

        if self.ai:
            return await self._ai_generate(commits, format)

        # Fallback: simple list.
        lines = ["# Changelog\n"]
        for c in commits:
            lines.append(f"- {c}")
        return "\n".join(lines)

    async def generate_next_entry(self, version: str, since_tag: str | None = None) -> str:
        """Generate entry for the next release."""
        commits = self._get_commits(since_tag)
        if not commits:
            return ""

        if self.ai:
            try:
                resp = await self.ai.chat(
                    messages=[{"role": "user", "content": (
                        f"Categorize these git commits into a changelog entry for version {version}.\n"
                        f"Use Keep a Changelog format (Added, Changed, Fixed, Removed, Security).\n\n"
                        + "\n".join(commits[:50])
                    )}],
                    system="You generate changelogs in Keep a Changelog format. Be concise.",
                )
                return getattr(resp, "content", "")
            except Exception:
                pass

        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines = [f"\n## [{version}] - {date}\n"]
        for c in commits:
            lines.append(f"- {c}")
        return "\n".join(lines)

    async def update_file(self, version: str) -> None:
        """Update CHANGELOG.md with new entry."""
        entry = await self.generate_next_entry(version)
        changelog_path = os.path.join(os.getcwd(), "CHANGELOG.md")

        if os.path.exists(changelog_path):
            existing = Path(changelog_path).read_text(encoding="utf-8")
            # Insert after header.
            if "# Changelog" in existing:
                parts = existing.split("# Changelog", 1)
                new_content = parts[0] + "# Changelog\n" + entry + "\n" + parts[1]
            else:
                new_content = existing + "\n" + entry
        else:
            new_content = "# Changelog\n\n" + entry

        Path(changelog_path).write_text(new_content, encoding="utf-8")
        self.console.print(f"  [green]✅ CHANGELOG.md updated with {version}[/]")

    async def suggest_version(self) -> str:
        """Suggest next semver based on changes."""
        commits = self._get_commits()
        if not commits:
            return "0.1.0"

        has_breaking = any("breaking" in c.lower() or "!" in c for c in commits)
        has_feat = any(c.lower().startswith("feat") for c in commits)

        current = self._get_current_version()
        parts = [int(x) for x in current.split(".")] if current else [0, 0, 0]
        while len(parts) < 3:
            parts.append(0)

        if has_breaking:
            parts[0] += 1; parts[1] = 0; parts[2] = 0
        elif has_feat:
            parts[1] += 1; parts[2] = 0
        else:
            parts[2] += 1

        return ".".join(str(p) for p in parts)

    async def _ai_generate(self, commits: list[str], format: str) -> str:
        try:
            resp = await self.ai.chat(
                messages=[{"role": "user", "content": (
                    f"Generate a changelog in {format} format from these commits:\n\n"
                    + "\n".join(commits[:100])
                )}],
                system="You generate professional changelogs. Group by version/date and categorize changes.",
            )
            return getattr(resp, "content", "")
        except Exception:
            return "# Changelog\n\n" + "\n".join(f"- {c}" for c in commits)

    def _get_commits(self, from_tag: str | None = None, to_tag: str | None = None) -> list[str]:
        try:
            import subprocess
            cmd = ["git", "log", "--oneline", "-100"]
            if from_tag and to_tag:
                cmd = ["git", "log", "--oneline", f"{from_tag}..{to_tag}"]
            elif from_tag:
                cmd = ["git", "log", "--oneline", f"{from_tag}..HEAD"]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except Exception:
            return []

    def _get_current_version(self) -> str:
        for fpath in ["pyproject.toml", "package.json", "Cargo.toml"]:
            full = os.path.join(os.getcwd(), fpath)
            if os.path.exists(full):
                try:
                    content = Path(full).read_text(encoding="utf-8")
                    match = re.search(r'"?version"?\s*[:=]\s*"([^"]+)"', content)
                    if match:
                        return match.group(1)
                except OSError:
                    pass
        return "0.0.0"
