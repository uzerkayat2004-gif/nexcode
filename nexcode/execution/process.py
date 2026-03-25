"""
NexCode Process Manager
~~~~~~~~~~~~~~~~~~~~~~~~

Tracks and manages long-running background processes such as
dev servers, file watchers, and test runners.  Provides output
capture, status display, and graceful cleanup.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.text import Text

from nexcode.execution.runner import CommandRunner

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OUTPUT_BUFFER_SIZE = 1000  # lines per process


# ---------------------------------------------------------------------------
# ProcessInfo
# ---------------------------------------------------------------------------


@dataclass
class ProcessInfo:
    """Live state of a managed background process."""

    process_id: str
    name: str
    command: str
    cwd: str
    pid: int
    started_at: float
    output_buffer: deque[str] = field(default_factory=lambda: deque(maxlen=_OUTPUT_BUFFER_SIZE))
    _reader_task: asyncio.Task[None] | None = field(default=None, repr=False)

    @property
    def elapsed_seconds(self) -> int:
        return int(time.time() - self.started_at)

    @property
    def elapsed_display(self) -> str:
        """Human-readable elapsed time."""
        seconds = self.elapsed_seconds
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        secs = seconds % 60
        if minutes < 60:
            return f"{minutes}m {secs}s"
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"


# ---------------------------------------------------------------------------
# ProcessManager
# ---------------------------------------------------------------------------


class ProcessManager:
    """
    Manages long-running background processes for NexCode.

    Provides start/stop lifecycle, output capture via ring buffers,
    Rich status display, and graceful shutdown on app exit.
    """

    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()
        self._processes: dict[str, ProcessInfo] = {}

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def start(
        self,
        command: str,
        name: str,
        *,
        cwd: str | None = None,
    ) -> str:
        """
        Start a background process and begin capturing output.

        Args:
            command: Shell command to run.
            name: Friendly name (e.g., "dev-server").
            cwd: Working directory.

        Returns:
            The process ID string.
        """
        process_id = await self.runner.run_background(command, name, cwd=cwd)

        # Retrieve the subprocess handle from the runner.
        proc = self.runner._background.get(process_id)
        meta = self.runner._background_meta.get(process_id, {})

        info = ProcessInfo(
            process_id=process_id,
            name=name,
            command=command,
            cwd=meta.get("cwd", ""),
            pid=meta.get("pid", 0),
            started_at=meta.get("started_at", time.time()),
        )

        # Start a background reader task to capture output.
        if proc and proc.stdout:
            info._reader_task = asyncio.create_task(self._read_output(process_id, proc))

        self._processes[process_id] = info
        return process_id

    async def stop(self, name_or_id: str) -> bool:
        """
        Stop a background process by name or ID.

        Returns True if a process was found and stopped.
        """
        process_id = self._resolve_id(name_or_id)
        if not process_id:
            return False

        info = self._processes.get(process_id)
        if info and info._reader_task:
            info._reader_task.cancel()
            try:
                await info._reader_task
            except asyncio.CancelledError:
                pass

        killed = await self.runner.kill(process_id)
        self._processes.pop(process_id, None)
        return killed

    async def get_output(
        self,
        name_or_id: str,
        last_n_lines: int = 50,
    ) -> str:
        """
        Get recent output from a background process.

        Args:
            name_or_id: Process name or ID.
            last_n_lines: Number of recent lines to return.

        Returns:
            The captured output as a string.
        """
        process_id = self._resolve_id(name_or_id)
        if not process_id:
            return "[Process not found]"

        info = self._processes.get(process_id)
        if not info:
            return "[Process not found]"

        lines = list(info.output_buffer)[-last_n_lines:]
        return "".join(lines) if lines else "[No output captured yet]"

    def is_running(self, name_or_id: str) -> bool:
        """Check if a process is still running."""
        process_id = self._resolve_id(name_or_id)
        if not process_id:
            return False

        proc = self.runner._background.get(process_id)
        return proc is not None and proc.returncode is None

    # ── Status display ─────────────────────────────────────────────────────

    def show_status(self, console: Console | None = None) -> str:
        """
        Display a Rich table of all background processes.

        Also returns a plain-text summary for the AI.
        """
        console = console or Console()

        if not self._processes:
            console.print("  [dim]No background processes running.[/dim]")
            return "No background processes running."

        table = Table(
            title="🔄 Background Processes",
            title_style="bold white",
            border_style="bright_black",
            show_lines=True,
            padding=(0, 1),
        )
        table.add_column("Name", style="bold white", min_width=12)
        table.add_column("Command", min_width=20)
        table.add_column("Status", min_width=8)
        table.add_column("Running For", min_width=10)

        lines: list[str] = []
        for pid, info in self._processes.items():
            running = self.is_running(pid)
            status = Text("✅ Up", style="bold green") if running else Text("❌ Down", style="red")
            elapsed = info.elapsed_display
            table.add_row(info.name, info.command, status, elapsed)
            lines.append(
                f"{info.name}: {info.command} — {'running' if running else 'stopped'} ({elapsed})"
            )

        console.print()
        console.print(table)
        console.print()

        return "\n".join(lines)

    # ── Cleanup ────────────────────────────────────────────────────────────

    async def cleanup_all(self) -> int:
        """
        Kill all background processes.  Called on app exit.

        Returns the number of processes stopped.
        """
        count = 0
        for pid in list(self._processes.keys()):
            await self.stop(pid)
            count += 1
        return count

    # ── Internal ───────────────────────────────────────────────────────────

    async def _read_output(
        self,
        process_id: str,
        proc: asyncio.subprocess.Process,
    ) -> None:
        """Background task that continuously reads process output."""
        info = self._processes.get(process_id)
        if not info or not proc.stdout:
            return

        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace")
                info.output_buffer.append(decoded)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    def _resolve_id(self, name_or_id: str) -> str | None:
        """Resolve a name or ID to a process ID."""
        # Direct ID match.
        if name_or_id in self._processes:
            return name_or_id

        # Name match.
        for pid, info in self._processes.items():
            if info.name == name_or_id:
                return pid

        return None

    @property
    def count(self) -> int:
        return len(self._processes)

    def __repr__(self) -> str:
        return f"ProcessManager(processes={self.count})"
