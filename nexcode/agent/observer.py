"""
NexCode Result Observer
~~~~~~~~~~~~~~~~~~~~~~~~

Observes tool results and agent behavior to detect
stuck loops, completion conditions, and suggest recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

@dataclass
class Observation:
    """Result of analyzing a tool execution."""

    success: bool
    key_findings: list[str] = field(default_factory=list)
    suggested_next_step: str | None = None
    needs_user_input: bool = False
    question_for_user: str | None = None


# ---------------------------------------------------------------------------
# ResultObserver
# ---------------------------------------------------------------------------

class ResultObserver:
    """
    Monitors the agentic loop for stuck patterns, task completion,
    and provides recovery suggestions when things go wrong.
    """

    # ── Stuck detection ────────────────────────────────────────────────────

    def is_stuck(self, steps: list[Any]) -> bool:
        """
        Detect if the agent is stuck in a loop.

        Patterns detected:
        - Same tool called with same params 3 times
        - 5 consecutive tool failures
        - No progress after 10 steps (all reads, no writes)
        """
        if len(steps) < 3:
            return False

        # Pattern 1: Same tool + same params 3 times in a row.
        if self._has_repeated_calls(steps, repeat_count=3):
            return True

        # Pattern 2: 5 consecutive failures.
        if self._has_consecutive_failures(steps, failure_count=5):
            return True

        # Pattern 3: 10 read-only steps with no writes.
        if self._has_no_progress(steps, window=10):
            return True

        return False

    def get_stuck_reason(self, steps: list[Any]) -> str:
        """Return a human-readable reason for why the agent is stuck."""
        if self._has_repeated_calls(steps, repeat_count=3):
            recent = steps[-1]
            tool_name = getattr(recent, "tool_name", "unknown")
            return f"Repeated call to '{tool_name}' with same parameters 3 times"

        if self._has_consecutive_failures(steps, failure_count=5):
            return "5 consecutive tool failures"

        if self._has_no_progress(steps, window=10):
            return "10 steps without any file modifications"

        return "Unknown stuck pattern"

    # ── Completion detection ───────────────────────────────────────────────

    def is_task_complete(self, ai_response: str, steps: list[Any]) -> bool:
        """
        Heuristic to detect if the AI considers the task done.

        The AI typically signals completion by providing a text
        response without requesting more tool calls.
        """
        if not ai_response:
            return False

        # Completion signals in AI responses.
        completion_phrases = [
            "task is complete",
            "changes are complete",
            "i've finished",
            "all done",
            "successfully completed",
            "implementation is complete",
            "the fix is in place",
            "everything is working",
            "here's what i did",
            "here is a summary",
            "let me know if",
        ]

        response_lower = ai_response.lower()
        return any(phrase in response_lower for phrase in completion_phrases)

    # ── Recovery suggestions ───────────────────────────────────────────────

    def suggest_recovery(self, steps: list[Any]) -> str:
        """Suggest a recovery action when the agent is stuck."""
        if self._has_repeated_calls(steps, repeat_count=3):
            recent = steps[-1]
            tool_name = getattr(recent, "tool_name", "unknown")
            return (
                f"The agent is calling '{tool_name}' repeatedly. "
                f"Try rephrasing the instruction or Break the task "
                f"into smaller steps."
            )

        if self._has_consecutive_failures(steps, failure_count=5):
            errors = []
            for step in steps[-5:]:
                result = getattr(step, "tool_result", None)
                if result and hasattr(result, "error") and result.error:
                    errors.append(result.error)
            return (
                f"Multiple tool failures detected. Recent errors:\n"
                + "\n".join(f"  - {e}" for e in errors[-3:])
                + "\n\nTry checking file paths and permissions."
            )

        if self._has_no_progress(steps, window=10):
            return (
                "The agent has been exploring without making changes. "
                "Try giving more specific instructions about what to modify."
            )

        return "Try rephrasing the instruction or breaking it into smaller tasks."

    # ── Analyze a tool result ──────────────────────────────────────────────

    def analyze(
        self,
        tool_name: str,
        tool_result: Any,
    ) -> Observation:
        """Analyze a single tool result and extract key findings."""
        success = getattr(tool_result, "success", True)
        output = str(getattr(tool_result, "output", ""))
        error = getattr(tool_result, "error", None)

        findings: list[str] = []
        needs_input = False
        question = None

        if not success and error:
            findings.append(f"Failed: {error}")

            # Detect permission issues.
            if "permission" in str(error).lower():
                needs_input = True
                question = "Permission denied. Should I try with elevated privileges?"

            # Detect file not found.
            if "not found" in str(error).lower():
                findings.append("File or resource not found — path may be incorrect")

        # Detect large outputs that might fill context.
        if len(output) > 50_000:
            findings.append("Very large output — may consume significant context")

        return Observation(
            success=success,
            key_findings=findings,
            needs_user_input=needs_input,
            question_for_user=question,
        )

    # ── Internal detection helpers ─────────────────────────────────────────

    def _has_repeated_calls(self, steps: list[Any], repeat_count: int) -> bool:
        """Check if the same tool+params was called N times in a row."""
        if len(steps) < repeat_count:
            return False

        recent = steps[-repeat_count:]
        first_name = getattr(recent[0], "tool_name", None)
        first_input = getattr(recent[0], "tool_input", None)

        if not first_name:
            return False

        return all(
            getattr(s, "tool_name", None) == first_name
            and getattr(s, "tool_input", None) == first_input
            for s in recent
        )

    def _has_consecutive_failures(self, steps: list[Any], failure_count: int) -> bool:
        """Check for N consecutive tool failures."""
        if len(steps) < failure_count:
            return False

        recent = steps[-failure_count:]
        return all(
            getattr(getattr(s, "tool_result", None), "success", True) is False
            for s in recent
            if getattr(s, "tool_result", None) is not None
        )

    def _has_no_progress(self, steps: list[Any], window: int) -> bool:
        """Check if the last N steps are all read-only (no writes)."""
        if len(steps) < window:
            return False

        recent = steps[-window:]
        write_tools = {
            "write_file", "edit_file", "create_file", "delete_file",
            "move_file", "copy_file", "search_and_replace",
            "run_command", "run_script", "git_commit",
        }
        return not any(
            getattr(s, "tool_name", "") in write_tools
            for s in recent
        )
