"""
NexCode Shell Tools
~~~~~~~~~~~~~~~~~~~~

Nine shell execution tools for running commands, scripts, tests,
managing dependencies, background processes, and environment.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from nexcode.execution.process import ProcessManager
from nexcode.execution.runner import CommandRunner
from nexcode.tools.base import BaseTool, ToolResult

# ---------------------------------------------------------------------------
# Shared singletons — these will be overridden from the registry
# ---------------------------------------------------------------------------

_runner: CommandRunner | None = None
_process_mgr: ProcessManager | None = None


def _get_runner() -> CommandRunner:
    global _runner
    if _runner is None:
        _runner = CommandRunner()
    return _runner


def _get_process_mgr() -> ProcessManager:
    global _process_mgr
    if _process_mgr is None:
        _process_mgr = ProcessManager(runner=_get_runner())
    return _process_mgr


# ---------------------------------------------------------------------------
# Interpreter map for RunScriptTool
# ---------------------------------------------------------------------------

INTERPRETER_MAP: dict[str, list[str]] = {
    ".py": ["python"],
    ".js": ["node"],
    ".ts": ["npx", "ts-node"],
    ".sh": ["bash"],
    ".bash": ["bash"],
    ".ps1": ["powershell", "-File"],
    ".rb": ["ruby"],
    ".pl": ["perl"],
    ".lua": ["lua"],
    ".r": ["Rscript"],
    ".R": ["Rscript"],
}


# ---------------------------------------------------------------------------
# Test framework detection patterns
# ---------------------------------------------------------------------------

def _detect_test_framework(cwd: str) -> tuple[str, str] | None:
    """
    Auto-detect the test framework and return (command, framework_name).
    """
    root = Path(cwd)

    # Python: pytest
    if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "[tool.pytest" in content or "pytest" in content:
                    return ("python -m pytest -v", "pytest")
            except OSError:
                pass
        if (root / "pytest.ini").exists():
            return ("python -m pytest -v", "pytest")

    # Python fallback: any tests/ directory
    if (root / "tests").is_dir():
        return ("python -m pytest -v", "pytest")

    # JavaScript/TypeScript: jest / vitest / mocha
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            content = pkg_json.read_text(encoding="utf-8")
            if "vitest" in content:
                return ("npx vitest run", "vitest")
            elif "jest" in content:
                return ("npx jest", "jest")
            elif "mocha" in content:
                return ("npx mocha", "mocha")
            else:
                return ("npm test", "npm test")
        except OSError:
            pass

    # Rust: cargo test
    if (root / "Cargo.toml").exists():
        return ("cargo test", "cargo")

    # Go: go test
    if (root / "go.mod").exists():
        return ("go test ./...", "go test")

    return None


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------

def _detect_package_manager(cwd: str) -> tuple[str, str] | None:
    """
    Auto-detect the package manager and return (install_command, manager_name).
    """
    root = Path(cwd)

    # Python
    if (root / "pyproject.toml").exists():
        if shutil.which("uv"):
            return ("uv sync", "uv")
        return ("pip install -e .", "pip")
    if (root / "requirements.txt").exists():
        return ("pip install -r requirements.txt", "pip")

    # Node.js
    if (root / "package.json").exists():
        if (root / "pnpm-lock.yaml").exists():
            return ("pnpm install", "pnpm")
        if (root / "yarn.lock").exists():
            return ("yarn install", "yarn")
        if (root / "bun.lockb").exists():
            return ("bun install", "bun")
        return ("npm install", "npm")

    # Rust
    if (root / "Cargo.toml").exists():
        return ("cargo build", "cargo")

    # Go
    if (root / "go.mod").exists():
        return ("go mod download", "go")

    return None


# ═══════════════════════════════════════════════════════════════════════════
# 1. RunCommandTool ⭐
# ═══════════════════════════════════════════════════════════════════════════

class RunCommandTool(BaseTool):
    """Run a shell command with live output streaming."""

    name = "run_command"
    description = (
        "Run any shell command. Streams output live, shows exit code "
        "and duration. Returns full stdout/stderr to the AI."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory (default: project root).",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30).",
            },
        },
        "required": ["command"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        command: str = kwargs["command"]
        cwd: str | None = kwargs.get("cwd")
        timeout: int = kwargs.get("timeout", 30)

        runner = _get_runner()
        result = await runner.run(command, cwd=cwd, timeout=timeout)

        if result.timed_out:
            return ToolResult(
                success=False,
                output=f"Command timed out after {timeout}s.\n\n{result.output}",
                display=f"$ {command} — TIMED OUT ({timeout}s)",
                error=f"Timed out after {timeout}s",
                metadata={"exit_code": result.exit_code, "duration_ms": result.duration_ms},
            )

        if result.success:
            return ToolResult.ok(
                output=f"Exit code: {result.exit_code}\nDuration: {result.duration_ms}ms\n\n{result.output}",
                display=f"$ {command} — exit {result.exit_code} ({result.duration_ms}ms)",
                exit_code=result.exit_code,
                duration_ms=result.duration_ms,
            )
        else:
            return ToolResult(
                success=False,
                output=f"Exit code: {result.exit_code}\nDuration: {result.duration_ms}ms\n\n{result.output}",
                display=f"$ {command} — FAILED exit {result.exit_code}",
                error=f"Command failed with exit code {result.exit_code}",
                metadata={"exit_code": result.exit_code, "duration_ms": result.duration_ms},
            )


# ═══════════════════════════════════════════════════════════════════════════
# 2. RunScriptTool
# ═══════════════════════════════════════════════════════════════════════════

class RunScriptTool(BaseTool):
    """Run a script file with auto-detected interpreter."""

    name = "run_script"
    description = (
        "Run a script file. Auto-detects the interpreter from the file "
        "extension (.py → python, .js → node, .sh → bash, etc.)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the script file.",
            },
            "args": {
                "type": "string",
                "description": "Arguments to pass to the script.",
            },
        },
        "required": ["path"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_str: str = kwargs["path"]
        args: str = kwargs.get("args", "")
        path = Path(path_str).resolve()

        if not path.is_file():
            return ToolResult.fail(f"Script not found: {path}")

        ext = path.suffix.lower()
        interpreter = INTERPRETER_MAP.get(ext)
        if not interpreter:
            return ToolResult.fail(
                f"Unknown script type: {ext}. "
                f"Supported: {', '.join(INTERPRETER_MAP.keys())}"
            )

        cmd_parts = interpreter + [str(path)]
        if args:
            cmd_parts.append(args)
        command = " ".join(cmd_parts)

        runner = _get_runner()
        result = await runner.run(command, cwd=str(path.parent), timeout=120)

        if result.success:
            return ToolResult.ok(
                output=f"Script completed (exit {result.exit_code}, {result.duration_ms}ms)\n\n{result.output}",
                display=f"Ran {path.name} — exit {result.exit_code}",
            )
        else:
            return ToolResult(
                success=False,
                output=f"Script failed (exit {result.exit_code})\n\n{result.output}",
                display=f"Script {path.name} FAILED — exit {result.exit_code}",
                error=f"Exit code {result.exit_code}",
            )


# ═══════════════════════════════════════════════════════════════════════════
# 3. RunTestsTool ⭐
# ═══════════════════════════════════════════════════════════════════════════

class RunTestsTool(BaseTool):
    """Auto-detect and run project tests."""

    name = "run_tests"
    description = (
        "Run project tests. Auto-detects the test framework (pytest, jest, "
        "vitest, cargo test, go test) and parses results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Project directory (default: current).",
            },
            "filter": {
                "type": "string",
                "description": "Filter to run specific tests (e.g., test name pattern).",
            },
        },
        "required": [],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        cwd: str = kwargs.get("path", os.getcwd())
        test_filter: str | None = kwargs.get("filter")

        detected = _detect_test_framework(cwd)
        if not detected:
            return ToolResult.fail(
                "No test framework detected. Ensure your project has "
                "pytest.ini, package.json, Cargo.toml, or go.mod."
            )

        command, framework = detected

        # Append filter if provided.
        if test_filter:
            if framework == "pytest":
                command += f" -k '{test_filter}'"
            elif framework in ("jest", "vitest"):
                command += f" --testNamePattern='{test_filter}'"
            elif framework == "cargo":
                command += f" {test_filter}"
            elif framework == "go test":
                command += f" -run '{test_filter}'"

        runner = _get_runner()
        result = await runner.run(command, cwd=cwd, timeout=300)

        # Parse test summary from output.
        summary = _parse_test_summary(result.output, framework)

        output = f"Framework: {framework}\nCommand: {command}\n"
        output += f"Exit code: {result.exit_code}\nDuration: {result.duration_ms}ms\n\n"
        output += summary + "\n\n" + result.output

        if result.success:
            return ToolResult.ok(
                output=output,
                display=f"🧪 Tests PASSED ({framework}) — {result.duration_ms}ms",
                framework=framework,
            )
        else:
            return ToolResult(
                success=False,
                output=output,
                display=f"🧪 Tests FAILED ({framework}) — exit {result.exit_code}",
                error=f"Tests failed with exit code {result.exit_code}",
                metadata={"framework": framework},
            )


# ═══════════════════════════════════════════════════════════════════════════
# 4. InstallDependenciesTool
# ═══════════════════════════════════════════════════════════════════════════

class InstallDependenciesTool(BaseTool):
    """Auto-detect and install project dependencies."""

    name = "install_dependencies"
    description = (
        "Install project dependencies. Auto-detects package manager "
        "(npm, pip, uv, cargo, go) and runs the appropriate install command."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Project directory (default: current).",
            },
        },
        "required": [],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        cwd: str = kwargs.get("path", os.getcwd())

        detected = _detect_package_manager(cwd)
        if not detected:
            return ToolResult.fail(
                "No package manager detected. Ensure your project has "
                "package.json, pyproject.toml, requirements.txt, Cargo.toml, or go.mod."
            )

        command, manager = detected

        runner = _get_runner()
        result = await runner.run(command, cwd=cwd, timeout=300)

        if result.success:
            return ToolResult.ok(
                output=f"Dependencies installed via {manager}\n\n{result.output}",
                display=f"📦 Installed dependencies ({manager})",
                manager=manager,
            )
        else:
            return ToolResult(
                success=False,
                output=f"Install failed ({manager})\n\n{result.output}",
                display=f"📦 Install FAILED ({manager})",
                error=f"Install failed with exit code {result.exit_code}",
            )


# ═══════════════════════════════════════════════════════════════════════════
# 5. StartBackgroundProcessTool
# ═══════════════════════════════════════════════════════════════════════════

class StartBackgroundProcessTool(BaseTool):
    """Start a long-running process in the background."""

    name = "start_background"
    description = (
        "Start a long-running process (dev server, watcher, etc.) in the "
        "background. Returns a process ID for tracking."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Command to run in background.",
            },
            "name": {
                "type": "string",
                "description": "Friendly name (e.g., 'dev-server').",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory.",
            },
        },
        "required": ["command", "name"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        command: str = kwargs["command"]
        name: str = kwargs["name"]
        cwd: str | None = kwargs.get("cwd")

        mgr = _get_process_mgr()

        try:
            pid = await mgr.start(command, name, cwd=cwd)
        except RuntimeError as exc:
            return ToolResult.fail(str(exc))

        return ToolResult.ok(
            output=f"Background process started: {name} (ID: {pid})",
            display=f"🔄 Started {name} in background",
            process_id=pid,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 6. StopBackgroundProcessTool
# ═══════════════════════════════════════════════════════════════════════════

class StopBackgroundProcessTool(BaseTool):
    """Stop a background process."""

    name = "stop_background"
    description = "Stop a background process by its name or process ID."
    parameters = {
        "type": "object",
        "properties": {
            "name_or_id": {
                "type": "string",
                "description": "Process name or ID to stop.",
            },
        },
        "required": ["name_or_id"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        name_or_id: str = kwargs["name_or_id"]
        mgr = _get_process_mgr()

        stopped = await mgr.stop(name_or_id)
        if stopped:
            return ToolResult.ok(
                output=f"Stopped: {name_or_id}",
                display=f"⏹ Stopped {name_or_id}",
            )
        else:
            return ToolResult.fail(f"Process not found: {name_or_id}")


# ═══════════════════════════════════════════════════════════════════════════
# 7. GetProcessOutputTool
# ═══════════════════════════════════════════════════════════════════════════

class GetProcessOutputTool(BaseTool):
    """Get recent output from a background process."""

    name = "get_process_output"
    description = "Get the recent output from a running background process."
    parameters = {
        "type": "object",
        "properties": {
            "name_or_id": {
                "type": "string",
                "description": "Process name or ID.",
            },
            "last_n_lines": {
                "type": "integer",
                "description": "Number of recent lines to return (default: 50).",
            },
        },
        "required": ["name_or_id"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        name_or_id: str = kwargs["name_or_id"]
        last_n: int = kwargs.get("last_n_lines", 50)

        mgr = _get_process_mgr()
        output = await mgr.get_output(name_or_id, last_n_lines=last_n)

        return ToolResult.ok(
            output=output,
            display=f"Output from {name_or_id} (last {last_n} lines)",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 8. WhichTool
# ═══════════════════════════════════════════════════════════════════════════

class WhichTool(BaseTool):
    """Check if a program is installed on the system."""

    name = "which"
    description = (
        "Check if a program is installed. Returns the path and version "
        "if found, or reports it as missing."
    )
    parameters = {
        "type": "object",
        "properties": {
            "program": {
                "type": "string",
                "description": "Name of the program to check (e.g., 'node', 'python').",
            },
        },
        "required": ["program"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        program: str = kwargs["program"]

        path = shutil.which(program)
        if not path:
            return ToolResult.ok(
                output=f"{program}: not found",
                display=f"❌ {program} — not installed",
                installed=False,
            )

        # Try to get version.
        version = "unknown"
        runner = _get_runner()
        for flag in ("--version", "-version", "-v", "version"):
            result = await runner.run(f"{program} {flag}", timeout=5)
            if result.success and result.stdout.strip():
                # Extract first line of version output.
                version = result.stdout.strip().splitlines()[0]
                break

        return ToolResult.ok(
            output=f"{program}: {path}\nVersion: {version}",
            display=f"✅ {program} — {path}",
            installed=True,
            path=path,
            version=version,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 9. SetEnvironmentTool
# ═══════════════════════════════════════════════════════════════════════════

class SetEnvironmentTool(BaseTool):
    """Set an environment variable for the NexCode session."""

    name = "set_environment"
    description = (
        "Set an environment variable that persists for all commands "
        "run in this NexCode session."
    )
    parameters = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Environment variable name.",
            },
            "value": {
                "type": "string",
                "description": "Value to set.",
            },
        },
        "required": ["key", "value"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        key: str = kwargs["key"]
        value: str = kwargs["value"]

        runner = _get_runner()
        runner.set_env(key, value)

        # Also set in the current Python process.
        os.environ[key] = value

        return ToolResult.ok(
            output=f"Set {key}={value}",
            display=f"🔧 {key}={value}",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_test_summary(output: str, framework: str) -> str:
    """Extract a test summary from framework output."""
    lines = output.strip().splitlines()

    # pytest: "X passed, Y failed, Z skipped"
    if framework == "pytest":
        for line in reversed(lines):
            if "passed" in line or "failed" in line:
                return line.strip()

    # jest: "Tests: X passed, Y failed, Z total"
    if framework in ("jest", "vitest"):
        for line in reversed(lines):
            if "Tests:" in line or "Test Suites:" in line:
                return line.strip()

    # cargo: "test result: ok. X passed; Y failed"
    if framework == "cargo":
        for line in reversed(lines):
            if "test result" in line:
                return line.strip()

    # go: "ok" or "FAIL"
    if framework == "go test":
        for line in reversed(lines):
            if line.startswith("ok") or line.startswith("FAIL"):
                return line.strip()

    return "Test summary not parsed."
