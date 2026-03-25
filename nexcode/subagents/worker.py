"""
NexCode Subagent Worker
~~~~~~~~~~~~~~~~~~~~~~~~~

An independent AI agent that runs a subtask with
restricted tools, step limits, and timeout.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SubagentConfig:
    """Configuration for spawning a subagent."""

    id: str = ""
    name: str = ""
    instruction: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    context: str | None = None
    max_steps: int = 20
    model: str | None = None
    provider: str | None = None
    timeout_seconds: int = 120


@dataclass
class SubagentResult:
    """Result of a subagent execution."""

    id: str = ""
    name: str = ""
    success: bool = False
    result: str = ""
    steps_taken: int = 0
    tools_used: list[str] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0
    token_usage: int = 0
    cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# SubagentWorker
# ---------------------------------------------------------------------------


class SubagentWorker:
    """
    An independent subagent that executes a task with its own
    context, restricted tools, and step/timeout limits.
    """

    def __init__(
        self,
        config: SubagentConfig,
        ai_provider: Any = None,
        tool_registry: Any = None,
        checkpoint_manager: Any = None,
    ) -> None:
        self.config = config
        if not self.config.id:
            self.config.id = f"sub_{uuid.uuid4().hex[:8]}"
        self.ai_provider = ai_provider
        self.tool_registry = tool_registry
        self.checkpoint_manager = checkpoint_manager

        self._status = "idle"
        self._current_step = 0
        self._tools_used: list[str] = []
        self._files_created: list[str] = []
        self._files_modified: list[str] = []
        self._progress: list[str] = []
        self._aborted = False

    # ── Run ────────────────────────────────────────────────────────────────

    async def run(self) -> SubagentResult:
        """Run the subagent to completion."""
        start = time.perf_counter()
        self._status = "running"

        try:
            result_text = await asyncio.wait_for(
                self._execute_loop(),
                timeout=self.config.timeout_seconds,
            )
            elapsed = int((time.perf_counter() - start) * 1000)
            self._status = "done"

            return SubagentResult(
                id=self.config.id,
                name=self.config.name,
                success=True,
                result=result_text,
                steps_taken=self._current_step,
                tools_used=self._tools_used,
                files_created=self._files_created,
                files_modified=self._files_modified,
                duration_ms=elapsed,
            )

        except TimeoutError:
            elapsed = int((time.perf_counter() - start) * 1000)
            self._status = "timeout"
            return SubagentResult(
                id=self.config.id,
                name=self.config.name,
                error=f"Timeout after {self.config.timeout_seconds}s",
                steps_taken=self._current_step,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = int((time.perf_counter() - start) * 1000)
            self._status = "failed"
            return SubagentResult(
                id=self.config.id,
                name=self.config.name,
                error=str(exc),
                steps_taken=self._current_step,
                duration_ms=elapsed,
            )

    async def _execute_loop(self) -> str:
        """Core execution loop — think → act → observe."""
        if not self.ai_provider:
            return "No AI provider available"

        messages: list[dict[str, Any]] = []

        # Build system message.
        system = (
            f"You are a focused subagent. Your task: {self.config.instruction}\n"
            "Complete the task efficiently. Use only the tools available to you.\n"
            "When done, provide a brief summary of what you accomplished."
        )
        if self.config.context:
            system += f"\n\nContext:\n{self.config.context}"

        messages.append({"role": "user", "content": self.config.instruction})

        # Get available tools.
        tools_schema: list[dict[str, Any]] = []
        if self.tool_registry:
            all_tools = self.tool_registry.get_all()
            for name, tool in all_tools.items():
                if not self.config.allowed_tools or name in self.config.allowed_tools:
                    tools_schema.append(tool.to_api_schema())

        last_response = ""

        for step in range(self.config.max_steps):
            if self._aborted:
                return "Aborted by user"

            self._current_step = step + 1
            self._progress.append(f"Step {self._current_step}")

            try:
                response = await self.ai_provider.chat(
                    messages=messages,
                    system=system,
                    tools=tools_schema or None,
                    model=self.config.model,
                )

                # Check for tool use.
                tool_calls = getattr(response, "tool_calls", None)
                if not tool_calls:
                    last_response = getattr(response, "content", str(response))
                    break

                # Execute tool calls concurrently.
                async def execute_single_tool(
                    tc: dict[str, Any],
                ) -> tuple[dict[str, Any], bool, str]:
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("arguments", {})
                    self._tools_used.append(tool_name)

                    if self.tool_registry and tool_name in self.tool_registry.get_all():
                        result = await self.tool_registry.execute(tool_name, tool_args)
                        result_text = getattr(result, "output", str(result))

                        # Track files.
                        path = tool_args.get("path", tool_args.get("file_path", ""))
                        if path:
                            if tool_name in ("create_file", "write_file"):
                                self._files_created.append(path)
                            elif tool_name in ("edit_file", "search_and_replace"):
                                self._files_modified.append(path)

                        return tc, True, result_text
                    else:
                        return tc, False, f"Tool '{tool_name}' not available"

                tasks = [execute_single_tool(tc) for tc in tool_calls]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, result in enumerate(results):
                    tc = tool_calls[i]
                    if isinstance(result, Exception):
                        tool_name = tc.get("name", "unknown")
                        result_text = f"Tool '{tool_name}' failed with error: {result}"
                    else:
                        _, is_available, result_text = result

                    messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                    messages.append(
                        {
                            "role": "tool",
                            "content": result_text,
                            "tool_call_id": tc.get("id", ""),
                        }
                    )

            except Exception as exc:
                last_response = f"Error at step {self._current_step}: {exc}"
                break

        return last_response

    # ── Control ────────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        return {
            "id": self.config.id,
            "name": self.config.name,
            "status": self._status,
            "step": self._current_step,
            "max_steps": self.config.max_steps,
            "tools_used": len(self._tools_used),
        }

    async def abort(self) -> None:
        self._aborted = True
        self._status = "aborted"

    async def get_progress(self) -> AsyncIterator[str]:
        for msg in self._progress:
            yield msg
