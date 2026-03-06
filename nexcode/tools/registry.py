"""
NexCode Tool Registry
~~~~~~~~~~~~~~~~~~~~~~

Central registry that manages all available tools, handles
schema generation for AI APIs, and routes tool call execution.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

from nexcode.tools.base import BaseTool, PermissionManager, ToolResult


class ToolRegistry:
    """
    Master registry for all NexCode tools.

    Registers tool instances, generates API schemas, executes tool calls
    with permission checks, and supports enable/disable per tool.
    """

    def __init__(
        self,
        permission_manager: PermissionManager | None = None,
        console: Console | None = None,
    ) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._disabled: set[str] = set()
        self.permission_manager = permission_manager or PermissionManager()
        self.console = console or Console()

    # ── Registration ───────────────────────────────────────────────────────

    def register(self, tool: BaseTool) -> None:
        """Register a single tool instance."""
        self._tools[tool.name] = tool

    def register_all(self) -> None:
        """Register every built-in file, search, shell, and git tool."""
        # File tools.
        from nexcode.tools.file_tools import (
            CopyFileTool,
            CreateFileTool,
            DeleteFileTool,
            EditFileTool,
            FileInfoTool,
            ListDirectoryTool,
            MoveFileTool,
            ReadFileTool,
            WriteFileTool,
        )
        # Search tools.
        from nexcode.tools.search_tools import (
            FindFilesTool,
            ReadManyFilesTool,
            SearchAndReplaceTool,
            SearchTextTool,
        )
        # Shell tools.
        from nexcode.tools.shell_tools import (
            GetProcessOutputTool,
            InstallDependenciesTool,
            RunCommandTool,
            RunScriptTool,
            RunTestsTool,
            SetEnvironmentTool,
            StartBackgroundProcessTool,
            StopBackgroundProcessTool,
            WhichTool,
        )
        # Git tools.
        from nexcode.tools.git_tools import (
            GitBlameTool,
            GitBranchTool,
            GitCommitTool,
            GitCreateTagTool,
            GitDiffTool,
            GitLogTool,
            GitPullTool,
            GitPushTool,
            GitResetTool,
            GitRestoreFileTool,
            GitStageTool,
            GitStashTool,
            GitStatusTool,
            GitUnstageTool,
        )
        # Web tools.
        from nexcode.tools.web_tools import (
            CheckUrlTool,
            DeepResearchTool,
            FetchDocsTool,
            FetchPageTool,
            FindCodeExamplesTool,
            GetPackageInfoTool,
            WebSearchTool,
        )

        tools: list[BaseTool] = [
            # File tools (1-9)
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            CreateFileTool(),
            DeleteFileTool(),
            ListDirectoryTool(),
            MoveFileTool(),
            CopyFileTool(),
            FileInfoTool(),
            # Search tools (10-13)
            SearchTextTool(),
            FindFilesTool(),
            SearchAndReplaceTool(),
            ReadManyFilesTool(),
            # Shell tools (14-22)
            RunCommandTool(),
            RunScriptTool(),
            RunTestsTool(),
            InstallDependenciesTool(),
            StartBackgroundProcessTool(),
            StopBackgroundProcessTool(),
            GetProcessOutputTool(),
            WhichTool(),
            SetEnvironmentTool(),
            # Git tools (23-36)
            GitStatusTool(),
            GitDiffTool(),
            GitStageTool(),
            GitUnstageTool(),
            GitCommitTool(),
            GitPushTool(),
            GitPullTool(),
            GitLogTool(),
            GitBranchTool(),
            GitStashTool(),
            GitResetTool(),
            GitRestoreFileTool(),
            GitCreateTagTool(),
            GitBlameTool(),
            # Web tools (37-43)
            WebSearchTool(),
            FetchPageTool(),
            DeepResearchTool(),
            FindCodeExamplesTool(),
            GetPackageInfoTool(),
            FetchDocsTool(),
            CheckUrlTool(),
        ]

        for tool in tools:
            self.register(tool)

    # ── Schema generation ──────────────────────────────────────────────────

    def get_api_schemas(self) -> list[dict[str, Any]]:
        """
        Return tool definitions formatted for LLM APIs.

        Only includes enabled tools.
        """
        return [
            tool.to_api_schema()
            for name, tool in self._tools.items()
            if name not in self._disabled
        ]

    # ── Execution ──────────────────────────────────────────────────────────

    async def execute(
        self,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> ToolResult:
        """
        Execute a tool call by name.

        Handles permission checks, error catching, and result formatting.

        Args:
            tool_name: The registered name of the tool.
            parameters: The parameters to pass to the tool.

        Returns:
            A ``ToolResult`` with the outcome.
        """
        tool = self._tools.get(tool_name)

        if not tool:
            return ToolResult.fail(f"Unknown tool: '{tool_name}'")

        if tool_name in self._disabled:
            return ToolResult.fail(f"Tool '{tool_name}' is currently disabled.")

        # Permission check.
        if self.permission_manager.requires_permission(tool):
            target = parameters.get("path", parameters.get("source", ""))
            action = _summarize_action(tool_name, parameters)
            granted = self.permission_manager.request_permission(
                tool, action_summary=action, target=str(target),
            )
            if not granted:
                return ToolResult.fail("Permission denied by user.")

        # Execute the tool.
        try:
            result = await tool.execute(**parameters)
        except Exception as exc:
            return ToolResult.fail(f"Tool execution error: {exc}")

        return result

    # ── Enable / disable ───────────────────────────────────────────────────

    def enable(self, tool_name: str) -> None:
        """Re-enable a disabled tool."""
        self._disabled.discard(tool_name)

    def disable(self, tool_name: str) -> None:
        """Disable a tool (excluded from schemas and execution)."""
        self._disabled.add(tool_name)

    def is_enabled(self, tool_name: str) -> bool:
        """Check if a tool is currently enabled."""
        return tool_name in self._tools and tool_name not in self._disabled

    # ── Listing ────────────────────────────────────────────────────────────

    def list_tools(self) -> None:
        """Print a Rich-formatted table of all registered tools."""
        table = Table(
            title="NexCode — Registered Tools",
            title_style="bold white",
            border_style="bright_black",
            show_lines=True,
            padding=(0, 1),
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Tool", style="bold white", min_width=20)
        table.add_column("Type", min_width=10)
        table.add_column("Status", min_width=10)
        table.add_column("Description", max_width=50)

        for i, (name, tool) in enumerate(self._tools.items(), start=1):
            # Tool type label.
            if tool.is_read_only:
                kind = "[cyan]read[/]"
            elif tool.is_destructive:
                kind = "[red]write[/]"
            else:
                kind = "[yellow]action[/]"

            # Status.
            if name in self._disabled:
                status = "[dim]disabled[/]"
            else:
                status = "[green]active[/]"

            # Truncate description.
            desc = tool.description[:80]
            if len(tool.description) > 80:
                desc += "…"

            table.add_row(str(i), name, kind, status, desc)

        self.console.print()
        self.console.print(table)
        self.console.print(f"\n  [dim]{self.count} tools registered[/]")

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        """Total number of registered tools."""
        return len(self._tools)

    @property
    def active_count(self) -> int:
        """Number of enabled tools."""
        return len(self._tools) - len(self._disabled)

    def get(self, name: str) -> BaseTool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={list(self._tools.keys())})"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _summarize_action(tool_name: str, params: dict[str, Any]) -> str:
    """Generate a short human-readable action summary for permission prompts."""
    summaries: dict[str, str] = {
        "write_file": "Create or overwrite file",
        "edit_file": "Modify file content",
        "create_file": "Create new file",
        "delete_file": "Delete file (move to trash)",
        "move_file": "Move/rename file",
        "copy_file": "Copy file",
        "search_and_replace": "Replace text in multiple files",
        "run_command": "Execute shell command",
        "run_script": "Run script file",
        "run_tests": "Run project tests",
        "install_dependencies": "Install project dependencies",
        "start_background": "Start background process",
        "stop_background": "Stop background process",
        "set_environment": "Set environment variable",
    }
    return summaries.get(tool_name, f"Execute {tool_name}")
