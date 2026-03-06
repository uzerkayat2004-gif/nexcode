"""
NexCode Conversation History Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Manages the in-memory conversation history with support for
serialization, truncation, and role-based message storage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class Role(str, Enum):
    """Message role identifiers."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class Message:
    """A single conversation message."""
    role: Role
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict suitable for API calls."""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def to_api_format(self) -> dict[str, str]:
        """Return the minimal dict expected by most LLM APIs."""
        return {"role": self.role.value, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """Deserialize from a dict."""
        return cls(
            role=Role(data["role"]),
            content=data["content"],
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )


class ConversationHistory:
    """
    In-memory conversation history with serialization support.

    Stores messages in order and provides helpers for truncation,
    export, and API-formatted retrieval.
    """

    def __init__(self, system_prompt: str | None = None) -> None:
        self._messages: list[Message] = []
        self._system_prompt = system_prompt

        # If a system prompt is provided, prepend it.
        if system_prompt:
            self._messages.append(
                Message(role=Role.SYSTEM, content=system_prompt)
            )

    @property
    def messages(self) -> list[Message]:
        """Return all messages (read-only copy)."""
        return list(self._messages)

    @property
    def message_count(self) -> int:
        """Return the total number of messages."""
        return len(self._messages)

    def add(self, role: Role | str, content: str, **metadata: Any) -> Message:
        """
        Append a new message to the history.

        Args:
            role: The message role (user, assistant, system, tool).
            content: The message content.
            **metadata: Arbitrary metadata to attach.

        Returns:
            The created ``Message`` object.
        """
        if isinstance(role, str):
            role = Role(role)
        msg = Message(role=role, content=content, metadata=metadata)
        self._messages.append(msg)
        return msg

    def add_user(self, content: str) -> Message:
        """Shorthand: add a user message."""
        return self.add(Role.USER, content)

    def add_assistant(self, content: str) -> Message:
        """Shorthand: add an assistant message."""
        return self.add(Role.ASSISTANT, content)

    def add_tool_call(
        self, tool_use_id: str, tool_name: str, tool_input: dict
    ) -> None:
        """
        Record the AI's tool-use request in the conversation history.

        Uses the standard OpenAI tool calling format::

            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": ..., "type": "function",
                                "function": {"name": ..., "arguments": ...}}]
            }

        If the previous message is already an assistant message, the tool call
        is merged into its ``tool_calls`` list (parallel tool use).
        """
        import json as _json

        tool_call_block: dict[str, Any] = {
            "id": tool_use_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": _json.dumps(
                    tool_input if isinstance(tool_input, dict) else {}
                ),
            },
        }

        # Try to merge into the preceding assistant message.
        if self._messages:
            last = self._messages[-1]

            # Previous message is a raw assistant dict with tool_calls.
            if isinstance(last, dict) and last.get("role") == "assistant":
                last.setdefault("tool_calls", []).append(tool_call_block)
                return

            # Previous message is a Message(role=ASSISTANT) from add_assistant().
            if isinstance(last, Message) and last.role == Role.ASSISTANT:
                raw: dict[str, Any] = {
                    "role": "assistant",
                    "content": last.content or None,
                    "tool_calls": [tool_call_block],
                }
                self._messages[-1] = raw  # type: ignore[assignment]
                return

        # No preceding assistant message — create a new one.
        self._messages.append({  # type: ignore[arg-type]
            "role": "assistant",
            "content": None,
            "tool_calls": [tool_call_block],
        })

    def add_tool_result(
        self, tool_use_id: str, content: str, is_error: bool = False
    ) -> None:
        """
        Record a tool execution result in the conversation history.

        Uses the standard OpenAI format::

            {"role": "tool", "tool_call_id": "...", "content": "..."}

        Each tool result is its own message (OpenAI requires one ``tool``
        message per ``tool_call_id``).
        """
        result_content = content
        if is_error:
            result_content = f"[ERROR] {content}"

        self._messages.append({  # type: ignore[arg-type]
            "role": "tool",
            "tool_call_id": tool_use_id,
            "content": result_content,
        })

    def get_api_messages(self) -> list[dict[str, Any]]:
        """
        Return messages formatted for LLM API calls.

        Handles both ``Message`` objects (plain text) and raw dicts
        (tool call / tool result messages).
        """
        result: list[dict[str, Any]] = []
        for msg in self._messages:
            if isinstance(msg, dict):
                result.append(msg)
            else:
                result.append(msg.to_api_format())
        return result

    def clear(self, *, keep_system: bool = True) -> None:
        """
        Clear all messages.

        Args:
            keep_system: If True, preserve the system prompt message.
        """
        if keep_system and self._system_prompt:
            self._messages = [
                Message(role=Role.SYSTEM, content=self._system_prompt)
            ]
        else:
            self._messages.clear()

    def truncate(self, max_messages: int, *, keep_system: bool = True) -> int:
        """
        Trim history to the most recent *max_messages* messages.

        Args:
            max_messages: Maximum number of messages to keep.
            keep_system: If True, the system message is always preserved.

        Returns:
            The number of messages removed.
        """
        if len(self._messages) <= max_messages:
            return 0

        if keep_system and self._system_prompt:
            system_msg = self._messages[0]
            recent = self._messages[-(max_messages - 1):]
            removed = len(self._messages) - max_messages
            self._messages = [system_msg] + recent
        else:
            removed = len(self._messages) - max_messages
            self._messages = self._messages[-max_messages:]

        return removed

    # -- Serialization -------------------------------------------------------

    def to_json(self) -> str:
        """Serialize the full history to a JSON string."""
        return json.dumps(
            [msg.to_dict() for msg in self._messages],
            indent=2,
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, data: str) -> ConversationHistory:
        """Deserialize a history from a JSON string."""
        raw = json.loads(data)
        history = cls()
        history._messages = [Message.from_dict(m) for m in raw]
        return history

    def save(self, path: Path) -> None:
        """Save the conversation history to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> ConversationHistory:
        """Load a conversation history from a JSON file."""
        data = path.read_text(encoding="utf-8")
        return cls.from_json(data)

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return f"ConversationHistory(messages={len(self._messages)})"
