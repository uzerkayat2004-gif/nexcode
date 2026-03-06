"""
NexCode Agent Context Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Manages conversation history, token counting, system prompt
construction, context compaction, and session persistence.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SESSION_DIR = Path.home() / ".nexcode" / "sessions"
_APPROX_CHARS_PER_TOKEN = 4  # rough heuristic when tiktoken unavailable


# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are NexCode, an expert AI coding assistant running in the terminal.
You have access to full file system operations, shell execution, git
operations, and the ability to work autonomously until tasks are complete.

Current working directory: {cwd}
Operating system: {os_name}
Git branch: {git_branch}
Project: {project_name}

Your approach to every task:
1. EXPLORE first — understand the codebase before making changes
2. PLAN — think step by step about what needs to be done
3. EXECUTE — use tools methodically, one step at a time
4. VERIFY — run tests or check output to confirm changes work
5. SUMMARIZE — tell the user clearly what you did

Rules:
- Always read files before editing them
- Always verify changes work after making them
- Ask for clarification if the task is ambiguous
- Never guess file paths — use list_directory and find_files
- Prefer surgical edits (edit_file) over full rewrites (write_file)
- Run tests after making code changes
- Commit changes only when explicitly asked

{project_context}"""


# ---------------------------------------------------------------------------
# AgentContext
# ---------------------------------------------------------------------------

class AgentContext:
    """
    Manages the full conversation context for the agentic loop.

    Tracks messages, counts tokens, builds system prompts,
    handles context compaction, and persists sessions to disk.
    """

    def __init__(self, cwd: str | None = None, max_tokens: int = 200_000) -> None:
        self.cwd = cwd or os.getcwd()
        self.max_tokens = max_tokens
        self._messages: list[dict[str, Any]] = []
        self._system_prompt: str = ""
        self._token_count: int = 0
        self._project_context: str = ""
        self._session_id: str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._files_modified: list[str] = []

        # Load project context on init.
        self._load_project_context()
        self._system_prompt = self._build_system_prompt()

    # ── Message management ─────────────────────────────────────────────────

    def add_message(self, role: str, content: str | list[Any]) -> None:
        """Add a message to conversation history."""
        self._messages.append({"role": role, "content": content})
        self._update_token_count()

    def add_tool_result(self, tool_use_id: str, result: Any) -> None:
        """Add a tool result to conversation history (Anthropic format)."""
        content = [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": str(result.output) if hasattr(result, "output") else str(result),
            }
        ]
        self._messages.append({"role": "user", "content": content})
        self._update_token_count()

    def get_messages(self) -> list[dict[str, Any]]:
        """Return full conversation history."""
        return list(self._messages)

    def get_system_prompt(self) -> str:
        """Return the current system prompt."""
        return self._system_prompt

    # ── Token counting ─────────────────────────────────────────────────────

    def get_token_count(self) -> int:
        """Approximate token count of the full context."""
        return self._token_count

    def get_usage_percent(self) -> float:
        """Context usage as a percentage (0-100)."""
        if self.max_tokens == 0:
            return 0.0
        return min(100.0, (self._token_count / self.max_tokens) * 100)

    def get_usage_display(self) -> str:
        """Return a colored usage bar string for the prompt."""
        pct = self.get_usage_percent()
        filled = int(pct / 10)
        bar = "█" * filled + "░" * (10 - filled)
        return f"[{bar} {pct:.0f}%]"

    def get_usage_color(self) -> str:
        """Return color name based on usage level."""
        pct = self.get_usage_percent()
        if pct <= 60:
            return "green"
        elif pct <= 80:
            return "yellow"
        elif pct <= 95:
            return "bright_red"
        else:
            return "red"

    def needs_compaction(self) -> bool:
        """Check if context is getting too large."""
        return self.get_usage_percent() > 80

    # ── Context compaction ─────────────────────────────────────────────────

    async def compact(self, ai_provider: Any) -> str:
        """
        Compact conversation history by summarizing older messages.

        Keeps the system prompt and last few exchanges intact,
        summarizes everything in between into a condensed block.
        """
        if len(self._messages) < 6:
            return "Context too small to compact."

        # Keep last 4 messages (2 exchanges), summarize the rest.
        to_summarize = self._messages[:-4]
        to_keep = self._messages[-4:]

        # Build summary request.
        summary_text = ""
        for msg in to_summarize:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(block.get("text", block.get("content", "")))
                    for block in content
                    if isinstance(block, dict)
                )
            summary_text += f"[{role}]: {str(content)[:500]}\n"

        try:
            summary_prompt = (
                "Summarize this conversation concisely, preserving key facts, "
                "decisions, file paths mentioned, and changes made:\n\n"
                + summary_text
            )
            response = await ai_provider.chat(
                messages=[{"role": "user", "content": summary_prompt}],
                system="You are a conversation summarizer. Be very concise.",
            )
            condensed = response.content if hasattr(response, "content") else str(response)
        except Exception:
            # Fallback: keep first and last messages of the summarized block.
            condensed = f"[Earlier conversation with {len(to_summarize)} messages summarized]"

        # Replace history with condensed version.
        self._messages = [
            {"role": "user", "content": f"[Context summary]: {condensed}"},
            {"role": "assistant", "content": "Understood. I have the context from our earlier conversation."},
        ] + to_keep

        self._update_token_count()
        return f"Compacted {len(to_summarize)} messages into summary. Usage: {self.get_usage_percent():.0f}%"

    def clear(self) -> None:
        """Clear all conversation history."""
        self._messages.clear()
        self._token_count = 0
        self._files_modified.clear()

    # ── File tracking ──────────────────────────────────────────────────────

    def track_file_modified(self, path: str) -> None:
        """Record that a file was modified during this session."""
        if path not in self._files_modified:
            self._files_modified.append(path)

    def get_files_modified(self) -> list[str]:
        return list(self._files_modified)

    # ── Session persistence ────────────────────────────────────────────────

    def save(self) -> Path:
        """Save current context to disk."""
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        path = _SESSION_DIR / f"{self._session_id}.json"

        data = {
            "session_id": self._session_id,
            "cwd": self.cwd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "messages": self._messages,
            "files_modified": self._files_modified,
            "token_count": self._token_count,
        }

        path.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")
        return path

    def load(self, session_id: str) -> bool:
        """Load context from a previous session."""
        path = _SESSION_DIR / f"{session_id}.json"
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._session_id = data.get("session_id", session_id)
            self.cwd = data.get("cwd", self.cwd)
            self._messages = data.get("messages", [])
            self._files_modified = data.get("files_modified", [])
            self._update_token_count()
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    @property
    def session_id(self) -> str:
        return self._session_id

    # ── Project context ────────────────────────────────────────────────────

    def _load_project_context(self) -> None:
        """Load NEXCODE.md or similar project context file."""
        candidates = ["NEXCODE.md", "CLAUDE.md", "AI.md", ".nexcode/context.md"]
        for name in candidates:
            path = Path(self.cwd) / name
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    self._project_context = f"Project context from {name}:\n{content}"
                    return
                except OSError:
                    continue
        self._project_context = ""

    def get_project_summary(self) -> str:
        """Return the loaded project context."""
        return self._project_context or "No project context file found."

    # ── System prompt ──────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """Build the full system prompt with current context."""
        # Detect git branch.
        git_branch = "N/A"
        try:
            from nexcode.git.engine import GitEngine
            engine = GitEngine(self.cwd)
            if engine.is_git_repo():
                git_branch = engine.get_current_branch()
        except Exception:
            pass

        # Project name from directory.
        project_name = Path(self.cwd).name

        return SYSTEM_PROMPT_TEMPLATE.format(
            cwd=self.cwd,
            os_name=f"{platform.system()} {platform.release()}",
            git_branch=git_branch,
            project_name=project_name,
            project_context=self._project_context,
        )

    def rebuild_system_prompt(self) -> None:
        """Rebuild system prompt (e.g., after changing cwd)."""
        self._load_project_context()
        self._system_prompt = self._build_system_prompt()

    # ── Internal ───────────────────────────────────────────────────────────

    def _update_token_count(self) -> None:
        """Recalculate approximate token count."""
        total_chars = len(self._system_prompt)
        for msg in self._messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        total_chars += len(str(block.get("text", block.get("content", ""))))
                    else:
                        total_chars += len(str(block))
        self._token_count = total_chars // _APPROX_CHARS_PER_TOKEN

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return (
            f"AgentContext(messages={self.message_count}, "
            f"tokens≈{self._token_count}, "
            f"usage={self.get_usage_percent():.0f}%)"
        )
