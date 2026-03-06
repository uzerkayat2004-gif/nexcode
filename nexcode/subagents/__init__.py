"""Subagent system for NexCode."""

from nexcode.subagents.coordinator import CoordinatorResult, TaskCoordinator
from nexcode.subagents.manager import SubagentManager
from nexcode.subagents.pool import AgentPool
from nexcode.subagents.worker import SubagentConfig, SubagentResult, SubagentWorker

__all__ = [
    "AgentPool",
    "CoordinatorResult",
    "SubagentConfig",
    "SubagentManager",
    "SubagentResult",
    "SubagentWorker",
    "TaskCoordinator",
]
