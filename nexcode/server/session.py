"""
NexCode Web Session Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Manages multiple independent chat sessions for the web UI.
Each session has its own ConversationHistory and NexCode engine instance.
"""

from __future__ import annotations

import uuid
import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from nexcode.ai.auth import AuthManager
from nexcode.ai.provider import AIProvider
from nexcode.config import NexCodeConfig, load_config
from nexcode.history import ConversationHistory
from nexcode.tools.registry import ToolRegistry


@dataclass
class ChatSession:
    """A single chat session with its own history and engine."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    title: str = "New Chat"
    history: ConversationHistory = field(default_factory=ConversationHistory)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    message_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_count": self.message_count,
        }


class WebSessionManager:
    """
    Manages multiple chat sessions for the web interface.

    Each session shares the same AI provider and tool registry,
    but has its own conversation history.
    """

    def __init__(self, config: NexCodeConfig | None = None) -> None:
        self.config = config or load_config()
        self.auth = AuthManager(api_keys=dict(self.config.api_keys))
        self.provider = AIProvider(config=self.config, auth=self.auth)
        self.tool_registry = ToolRegistry()
        self.tool_registry.register_all()
        # Set permissions to auto for web (no terminal prompts).
        self.tool_registry.permission_manager.mode = "auto"

        self._sessions: dict[str, ChatSession] = {}

    def create_session(self, title: str = "New Chat") -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(title=title)
        self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions, newest first."""
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True,
        )
        return [s.to_dict() for s in sessions]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    async def process_message(
        self, session_id: str, user_input: str
    ) -> dict[str, Any]:
        """
        Process a user message in a session and run the agentic loop.

        Returns a dict with the AI response and any tool calls that occurred.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        session.history.add_user(user_input)
        session.message_count += 1

        tools = self.tool_registry.get_api_schemas()
        tool_calls_log: list[dict[str, Any]] = []
        final_content = ""
        max_iterations = 10

        for _ in range(max_iterations):
            response = await self.provider.chat(
                messages=session.history.get_api_messages(),
                tools=tools,
            )

            if response.content:
                session.history.add_assistant(response.content)
                final_content = response.content

            if not response.tool_calls:
                break

            for call in response.tool_calls:
                session.history.add_tool_call(call.id, call.name, call.arguments)

                result = await self.tool_registry.execute(
                    tool_name=call.name,
                    parameters=call.arguments,
                )

                session.history.add_tool_result(
                    call.id, result.output, not result.success
                )

                tool_calls_log.append({
                    "id": call.id,
                    "tool": call.name,
                    "arguments": call.arguments,
                    "result": result.output[:2000],
                    "success": result.success,
                })

        # Auto-title from first message.
        if session.message_count == 1 and user_input:
            session.title = user_input[:60] + ("..." if len(user_input) > 60 else "")

        session.updated_at = datetime.now(UTC)
        session.message_count += 1

        return {
            "content": final_content,
            "tool_calls": tool_calls_log,
            "model": self.provider.current_model,
            "provider": self.provider.current_provider,
        }
