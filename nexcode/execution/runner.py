"""
NexCode Command Runner
~~~~~~~~~~~~~~~~~~~~~~~

Async subprocess execution engine with streaming output,
timeout handling, pipeline execution, and background process support.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from nexcode.execution.sandbox import PlatformAdapter, Sandbox

# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """Result of a completed command execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    success: bool
    timed_out: bool = False
    killed: bool = False

    @property
    def output(self) -> str:
        """Combined stdout + stderr for convenience."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_OUTPUT_BYTES = 1_048_576  # 1 MB cap on captured output
_DEFAULT_TIMEOUT = 30          # seconds


# ---------------------------------------------------------------------------
# CommandRunner
# ---------------------------------------------------------------------------

class CommandRunner:
    """
    Async command execution engine for NexCode.

    Runs shell commands via subprocess, handles timeouts, streams
    output in real time, and supports background processes.
    """

    def __init__(self, sandbox: Sandbox | None = None) -> None:
        self.sandbox = sandbox or Sandbox()
        self._env_overrides: dict[str, str] = {}
        self._background: dict[str, asyncio.subprocess.Process] = {}
        self._background_meta: dict[str, dict[str, Any]] = {}

    # ── Main execution ─────────────────────────────────────────────────────

    async def run(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
        env: dict[str, str] | None = None,
        stream_output: bool = False,
    ) -> ExecutionResult:
        """
        Run a shell command and return the captured result.

        Args:
            command: The shell command to execute.
            cwd: Working directory (defaults to cwd).
            timeout: Seconds before the process is killed.
            env: Extra environment variables to set.
            stream_output: If True, pipe output to a callback (not used here).

        Returns:
            An ``ExecutionResult`` with stdout, stderr, exit code, etc.
        """
        # Safety check.
        check = self.sandbox.check(command)
        if not check.allowed:
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"BLOCKED: {check.reason}",
                duration_ms=0,
                success=False,
            )

        # Build environment.
        run_env = {**os.environ, **self._env_overrides}
        if env:
            run_env.update(env)

        # Build shell command.
        shell_cmd = PlatformAdapter.get_shell()

        start = time.perf_counter()
        timed_out = False
        killed = False

        try:
            proc = await asyncio.create_subprocess_exec(
                *shell_cmd,
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=run_env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except TimeoutError:
                proc.kill()
                stdout_bytes, stderr_bytes = await proc.communicate()
                timed_out = True
                killed = True

        except FileNotFoundError as exc:
            elapsed = int((time.perf_counter() - start) * 1000)
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Shell not found: {exc}",
                duration_ms=elapsed,
                success=False,
            )
        except OSError as exc:
            elapsed = int((time.perf_counter() - start) * 1000)
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Execution error: {exc}",
                duration_ms=elapsed,
                success=False,
            )

        elapsed = int((time.perf_counter() - start) * 1000)

        # Decode and cap output.
        stdout = _decode_output(stdout_bytes)
        stderr = _decode_output(stderr_bytes)

        exit_code = proc.returncode or 0

        return ExecutionResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=elapsed,
            success=(exit_code == 0 and not timed_out),
            timed_out=timed_out,
            killed=killed,
        )

    # ── Streaming execution ────────────────────────────────────────────────

    async def run_streaming(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout: int = 120,
    ) -> AsyncIterator[str]:
        """
        Run a command and yield output lines in real time.

        Yields combined stdout + stderr as they arrive.
        """
        check = self.sandbox.check(command)
        if not check.allowed:
            yield f"BLOCKED: {check.reason}\n"
            return

        run_env = {**os.environ, **self._env_overrides}
        shell_cmd = PlatformAdapter.get_shell()

        proc = await asyncio.create_subprocess_exec(
            *shell_cmd,
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
            env=run_env,
        )

        total_bytes = 0

        try:
            async def _read_with_timeout() -> None:
                nonlocal total_bytes
                assert proc.stdout is not None
                while True:
                    line = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=timeout
                    )
                    if not line:
                        break
                    total_bytes += len(line)
                    if total_bytes > _MAX_OUTPUT_BYTES:
                        break
                    yield line.decode("utf-8", errors="replace")  # type: ignore[misc]

            # We can't yield inside an inner async function, so inline the loop.
            assert proc.stdout is not None
            while True:
                try:
                    line = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=timeout
                    )
                except TimeoutError:
                    proc.kill()
                    yield "[Timed out]\n"
                    break

                if not line:
                    break

                total_bytes += len(line)
                if total_bytes > _MAX_OUTPUT_BYTES:
                    yield "[Output truncated — exceeded 1MB]\n"
                    break

                yield line.decode("utf-8", errors="replace")

        finally:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()

    # ── Pipeline execution ─────────────────────────────────────────────────

    async def run_pipeline(
        self,
        commands: list[str],
        *,
        cwd: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> list[ExecutionResult]:
        """
        Run multiple commands in sequence, stopping on first failure.
        """
        results: list[ExecutionResult] = []
        for cmd in commands:
            result = await self.run(cmd, cwd=cwd, timeout=timeout)
            results.append(result)
            if not result.success:
                break
        return results

    # ── Background processes ───────────────────────────────────────────────

    async def run_background(
        self,
        command: str,
        name: str,
        *,
        cwd: str | None = None,
    ) -> str:
        """
        Start a command in the background (non-blocking).

        Returns a process ID string for tracking.
        """
        check = self.sandbox.check(command)
        if not check.allowed:
            raise RuntimeError(f"Command blocked: {check.reason}")

        run_env = {**os.environ, **self._env_overrides}
        shell_cmd = PlatformAdapter.get_shell()

        proc = await asyncio.create_subprocess_exec(
            *shell_cmd,
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
            env=run_env,
        )

        process_id = f"{name}-{proc.pid}"
        self._background[process_id] = proc
        self._background_meta[process_id] = {
            "name": name,
            "command": command,
            "cwd": cwd or os.getcwd(),
            "pid": proc.pid,
            "started_at": time.time(),
        }

        return process_id

    async def kill(self, process_id: str) -> bool:
        """Kill a background process by its ID."""
        proc = self._background.get(process_id)
        if not proc:
            return False

        try:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass

        self._background.pop(process_id, None)
        self._background_meta.pop(process_id, None)
        return True

    def list_background(self) -> list[dict[str, Any]]:
        """Return info about all background processes."""
        result: list[dict[str, Any]] = []
        for pid, meta in self._background_meta.items():
            proc = self._background.get(pid)
            is_running = proc is not None and proc.returncode is None
            elapsed = time.time() - meta["started_at"]
            result.append({
                "process_id": pid,
                "name": meta["name"],
                "command": meta["command"],
                "running": is_running,
                "elapsed_seconds": int(elapsed),
            })
        return result

    # ── Environment ────────────────────────────────────────────────────────

    def set_env(self, key: str, value: str) -> None:
        """Set an environment variable for all future commands."""
        self._env_overrides[key] = value

    def get_env(self, key: str) -> str | None:
        """Get the value of an environment override."""
        return self._env_overrides.get(key) or os.environ.get(key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_output(data: bytes) -> str:
    """Decode subprocess output with size cap and encoding fallback."""
    if len(data) > _MAX_OUTPUT_BYTES:
        data = data[:_MAX_OUTPUT_BYTES]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")
