"""Execution engine for NexCode — shell commands, processes, and sandboxing."""

from nexcode.execution.process import ProcessManager
from nexcode.execution.runner import CommandRunner, ExecutionResult
from nexcode.execution.sandbox import PlatformAdapter, Sandbox, SandboxResult

__all__ = [
    "CommandRunner",
    "ExecutionResult",
    "PlatformAdapter",
    "ProcessManager",
    "Sandbox",
    "SandboxResult",
]
