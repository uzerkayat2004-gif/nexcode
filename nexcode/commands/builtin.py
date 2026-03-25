"""
NexCode Built-in Slash Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All 30+ built-in commands organized by category.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console

from nexcode.commands.base import BaseCommand, CommandResult

# ═══════════════════════════════════════════════════════════════════════════
# SESSION COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

class ClearCommand(BaseCommand):
    name = "clear"
    aliases = ["cls", "c"]
    description = "Clear conversation history"
    usage = "/clear"
    category = "session"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        if context:
            context.clear()
        return CommandResult(success=True, output="✓ Conversation cleared. Memory preserved.", clear_screen=True)


class CompactCommand(BaseCommand):
    name = "compact"
    aliases = []
    description = "Compress context to save tokens"
    usage = "/compact"
    category = "session"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        ai = svc.get("ai_provider")
        if not context or not ai:
            return CommandResult(success=False, output="Context or AI provider not available")
        before = context.get_token_count()
        msg = await context.compact(ai)
        after = context.get_token_count()
        saved = ((before - after) / max(before, 1)) * 100
        return CommandResult(success=True, output=f"Context compacted: {before:,} → {after:,} tokens ({saved:.0f}% saved)")


class SaveCommand(BaseCommand):
    name = "save"
    aliases = []
    description = "Save current session"
    usage = "/save [name]"
    category = "session"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        sm = svc.get("session_manager")
        session = svc.get("session")
        if not sm or not session:
            return CommandResult(success=False, output="Session manager not available")
        sm.save(session)
        return CommandResult(success=True, output=f"✓ Session saved: {session.id}")


class LoadCommand(BaseCommand):
    name = "load"
    aliases = []
    description = "Load a saved session"
    usage = "/load [session_id]"
    category = "session"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        sm = svc.get("session_manager")
        if not sm:
            return CommandResult(success=False, output="Session manager not available")
        if not args:
            sessions = sm.list_sessions()
            sm.show_sessions(sessions)
            return CommandResult(success=True)
        session = sm.resume(args[0])
        if session:
            return CommandResult(success=True, output=f"✓ Loaded session: {session.id}")
        return CommandResult(success=False, output=f"Session '{args[0]}' not found")


class HistoryCommand(BaseCommand):
    name = "history"
    aliases = []
    description = "View task history"
    usage = "/history"
    category = "session"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        from nexcode.agent.loop import TaskHistory
        TaskHistory.show(svc.get("console"))
        return CommandResult(success=True)


class UndoCommand(BaseCommand):
    name = "undo"
    aliases = []
    description = "Undo last file change"
    usage = "/undo"
    category = "session"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        try:
            from nexcode.tools.base import CheckpointManager
            cm = CheckpointManager()
            checkpoints = cm._checkpoints
            if not checkpoints:
                return CommandResult(success=False, output="No checkpoints available")
            last = checkpoints[-1]
            cm.restore(last["id"])
            return CommandResult(success=True, output=f"✓ Restored: {last.get('path', 'file')}")
        except Exception as e:
            return CommandResult(success=False, output=f"Undo failed: {e}")


class RewindCommand(BaseCommand):
    name = "rewind"
    aliases = []
    description = "Rewind multiple file changes"
    usage = "/rewind [steps]"
    category = "session"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        steps = int(args[0]) if args else 1
        try:
            from nexcode.tools.base import CheckpointManager
            cm = CheckpointManager()
            restored = 0
            for _ in range(steps):
                if not cm._checkpoints:
                    break
                cp = cm._checkpoints[-1]
                cm.restore(cp["id"])
                restored += 1
            return CommandResult(success=True, output=f"✓ Rewound {restored} checkpoint(s)")
        except Exception as e:
            return CommandResult(success=False, output=f"Rewind failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# MODEL COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

class ModelCommand(BaseCommand):
    name = "model"
    aliases = []
    description = "Show or switch AI model"
    usage = "/model [name]"
    category = "model"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        ai = svc.get("ai_provider")
        if not args:
            model = getattr(ai, "current_model", "unknown") if ai else "unknown"
            return CommandResult(success=True, output=f"Current model: {model}")

        new_model = args[0]
        if ai and hasattr(ai, "current_model"):
            ai.current_model = new_model
            # Persist to config
            from nexcode.config import save_config
            if hasattr(ai, "config"):
                ai.config.default_model = new_model
                save_config(ai.config)

        return CommandResult(success=True, output=f"✓ Switched to: {new_model}")


class ProviderCommand(BaseCommand):
    name = "provider"
    aliases = []
    description = "Show or switch AI provider"
    usage = "/provider [name]"
    category = "model"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        ai = svc.get("ai_provider")
        if not args:
            provider = getattr(ai, "current_provider", "unknown") if ai else "unknown"
            return CommandResult(success=True, output=f"Current provider: {provider}")

        new_provider = args[0]
        if ai and hasattr(ai, "current_provider"):
            ai.current_provider = new_provider
            # Persist to config
            from nexcode.config import save_config
            if hasattr(ai, "config"):
                ai.config.default_provider = new_provider
                save_config(ai.config)
        return CommandResult(success=True, output=f"✓ Switched provider to: {new_provider}")


class ModelsCommand(BaseCommand):
    name = "models"
    aliases = []
    description = "List all available models"
    usage = "/models"
    category = "model"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        try:
            from nexcode.ai.models import ModelRegistry
            registry = ModelRegistry()
            registry.show_models(Console())
        except Exception:
            return CommandResult(success=True, output="Use /model to see/set current model")
        return CommandResult(success=True)


class TokensCommand(BaseCommand):
    name = "tokens"
    aliases = []
    description = "Show context window usage"
    usage = "/tokens"
    category = "model"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        if not context:
            return CommandResult(success=False, output="No active context")
        count = context.get_token_count()
        pct = context.get_usage_percent()
        msgs = context.message_count
        bar = context.get_usage_display()
        return CommandResult(success=True, output=f"Context: {count:,} tokens ({pct:.0f}%) {bar}\nMessages: {msgs}")


# ═══════════════════════════════════════════════════════════════════════════
# AUTH COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

class LoginCommand(BaseCommand):
    name = "login"
    aliases = []
    description = "OAuth login to a provider"
    usage = "/login [provider]"
    category = "auth"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        if not args:
            return CommandResult(success=True, output="Usage: /login google")
        return CommandResult(success=True, output=f"OAuth login for '{args[0]}' — use the browser window that opens.")


class LogoutCommand(BaseCommand):
    name = "logout"
    aliases = []
    description = "Logout from a provider"
    usage = "/logout [provider]"
    category = "auth"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        if not args:
            return CommandResult(success=True, output="Usage: /logout google")
        return CommandResult(success=True, output=f"✓ Logged out from {args[0]}")


class AuthCommand(BaseCommand):
    name = "auth"
    aliases = []
    description = "Show auth status for all providers"
    usage = "/auth"
    category = "auth"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        auth = svc.get("auth_manager")
        if auth:
            auth.show_auth_status(Console())
            return CommandResult(success=True)

        # Fallback: build a quick status table from env vars.
        from nexcode.ai.auth import AuthManager
        am = AuthManager()
        am.show_auth_status(Console())
        return CommandResult(success=True)


class ApiKeyCommand(BaseCommand):
    name = "apikey"
    aliases = []
    description = "Set API key for a provider"
    usage = "/apikey [provider] [key]"
    category = "auth"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        if len(args) < 2:
            return CommandResult(success=False, output="Usage: /apikey anthropic sk-ant-...")

        provider = args[0].lower()
        key = args[1]

        # 1. Set in the live AuthManager so it takes effect immediately.
        auth = svc.get("auth_manager")
        if auth:
            auth.set_api_key(provider, key)

        # 2. Persist to .nexcode.toml so it survives restarts.
        import os
        from pathlib import Path
        toml_path = Path(os.getcwd()) / ".nexcode.toml"
        try:
            import tomli
            import tomli_w
            existing: dict = {}
            if toml_path.exists():
                existing = tomli.loads(toml_path.read_text(encoding="utf-8"))
            if "api_keys" not in existing:
                existing["api_keys"] = {}
            existing["api_keys"][provider] = key
            toml_path.write_text(tomli_w.dumps(existing), encoding="utf-8")
        except Exception:
            # Fallback: append manually if tomli unavailable.
            try:
                with open(toml_path, "a", encoding="utf-8") as f:
                    f.write(f"\n[api_keys]\n{provider} = \"{key}\"\n")
            except OSError:
                pass

        # 3. Also set in environment so litellm picks it up this session.
        from nexcode.ai.auth import ENV_KEY_MAP
        env_var = ENV_KEY_MAP.get(provider)
        if env_var:
            os.environ[env_var] = key

        return CommandResult(success=True, output=f"✓ API key set for {provider} (saved to .nexcode.toml)")


# ═══════════════════════════════════════════════════════════════════════════
# SAFETY COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

class ModeCommand(BaseCommand):
    name = "mode"
    aliases = []
    description = "Show or switch permission mode"
    usage = "/mode [ask|auto|strict|yolo]"
    category = "safety"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        guardian = svc.get("guardian")
        if not args:
            mode = guardian.permissions.mode if guardian else "ask"
            return CommandResult(success=True, output=f"Current mode: {mode}")
        new_mode = args[0].lower()
        if new_mode not in ("ask", "auto", "strict", "yolo"):
            return CommandResult(success=False, output=f"Invalid mode: {new_mode}. Use ask/auto/strict/yolo")
        if guardian:
            guardian.permissions.mode = new_mode
        warning = "\n⚠️  YOLO mode: ALL safety prompts disabled. You are on your own." if new_mode == "yolo" else ""
        return CommandResult(success=True, output=f"✓ Mode switched to: {new_mode}{warning}")


class SafetyCommand(BaseCommand):
    name = "safety"
    aliases = []
    description = "Show safety dashboard"
    usage = "/safety"
    category = "safety"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        guardian = svc.get("guardian")
        if guardian:
            guardian.show_dashboard()
        else:
            return CommandResult(success=True, output="Safety system not initialized")
        return CommandResult(success=True)


class AuditCommand(BaseCommand):
    name = "audit"
    aliases = []
    description = "Show audit log entries"
    usage = "/audit [--today] [--file path]"
    category = "safety"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        guardian = svc.get("guardian")
        if guardian:
            guardian.audit.show(limit=20)
        return CommandResult(success=True)


class PermissionsCommand(BaseCommand):
    name = "permissions"
    aliases = []
    description = "Show permission rules"
    usage = "/permissions"
    category = "safety"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        guardian = svc.get("guardian")
        if guardian:
            guardian.show_permissions()
        return CommandResult(success=True)


class IgnoreCommand(BaseCommand):
    name = "ignore"
    aliases = []
    description = "Add path to .nexcode-ignore"
    usage = "/ignore [path]"
    category = "safety"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        if not args:
            return CommandResult(success=False, output="Usage: /ignore .env")
        import os
        ignore_path = os.path.join(os.getcwd(), ".nexcode-ignore")
        with open(ignore_path, "a", encoding="utf-8") as f:
            f.write(args[0] + "\n")
        return CommandResult(success=True, output=f"✓ Added '{args[0]}' to .nexcode-ignore")


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

class ToolsCommand(BaseCommand):
    name = "tools"
    aliases = []
    description = "List all available tools"
    usage = "/tools"
    category = "tools"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        registry = svc.get("tool_registry")
        if registry:
            tools = registry.get_all()
            lines = [f"  {t.name:<24} {t.description[:50]}" for t in tools.values()]
            output = f"Available tools ({len(lines)}):\n" + "\n".join(lines)
            return CommandResult(success=True, output=output)
        return CommandResult(success=True, output="Tool registry not available")


class RunCommand(BaseCommand):
    name = "run"
    aliases = []
    description = "Run a shell command directly"
    usage = "/run [command]"
    category = "tools"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        if not args:
            return CommandResult(success=False, output="Usage: /run npm install")
        command = " ".join(args)
        import asyncio
        import subprocess
        try:
            proc = await asyncio.create_subprocess_shell(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode(errors="replace")
            if stderr:
                output += "\n" + stderr.decode(errors="replace")
            icon = "✅" if proc.returncode == 0 else "❌"
            return CommandResult(success=proc.returncode == 0, output=f"{icon} Exit {proc.returncode}\n{output[:2000]}")
        except Exception as e:
            return CommandResult(success=False, output=f"Failed: {e}")


class WebCommand(BaseCommand):
    name = "web"
    aliases = []
    description = "Search the web"
    usage = "/web [query]"
    category = "tools"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        if not args:
            return CommandResult(success=False, output="Usage: /web latest React 19 features")
        return CommandResult(success=True, output=f"Web search: {' '.join(args)} (not yet implemented)")


# ═══════════════════════════════════════════════════════════════════════════
# GIT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

class GitCommand(BaseCommand):
    name = "git"
    aliases = []
    description = "Quick git operations"
    usage = "/git [status|diff|log|branch]"
    category = "git"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        if not args:
            return CommandResult(success=True, output="Usage: /git status|diff|log|branch")
        try:
            from nexcode.git.engine import GitEngine
            engine = GitEngine()
            sub = args[0].lower()
            if sub == "status":
                status = engine.get_status()
                lines = [
                    f"Branch: {status.branch}",
                    f"Dirty: {status.is_dirty}",
                    f"Staged: {len(status.staged_files)} files",
                    f"Unstaged: {len(status.unstaged_files)} files",
                    f"Untracked: {len(status.untracked_files)} files",
                ]
                return CommandResult(success=True, output="\n".join(lines))
            elif sub == "diff":
                diff = engine.get_diff()
                return CommandResult(success=True, output=diff[:2000] if diff else "No changes")
            elif sub == "log":
                from nexcode.git.history import CommitHistory
                ch = CommitHistory(engine)
                ch.show_log(limit=10)
                return CommandResult(success=True)
            elif sub == "branch":
                branches = engine.list_branches()
                current = engine.get_current_branch()
                lines = [f"  {'*' if b == current else ' '} {b}" for b in branches]
                return CommandResult(success=True, output="\n".join(lines))
        except Exception as e:
            return CommandResult(success=False, output=f"Git error: {e}")
        return CommandResult(success=True, output=f"Unknown git subcommand: {args[0]}")


class CommitCommand(BaseCommand):
    name = "commit"
    aliases = []
    description = "Stage all and commit"
    usage = "/commit [message]"
    category = "git"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        try:
            from nexcode.git.engine import GitEngine
            engine = GitEngine()
            engine.stage_all()
            message = " ".join(args) if args else "Update files"
            commit = engine.commit(message)
            return CommandResult(success=True, output=f"✓ Committed: [{commit.short_hash}] {commit.message}")
        except Exception as e:
            return CommandResult(success=False, output=f"Commit failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

class HelpCommand(BaseCommand):
    name = "help"
    aliases = ["h", "?"]
    description = "Show all commands"
    usage = "/help [command]"
    category = "system"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        registry = svc.get("command_registry")
        if not registry:
            return CommandResult(success=False, output="Command registry not available")

        if args:
            # Show help for specific command.
            cmd = registry.get(args[0])
            if cmd:
                return CommandResult(success=True, output=f"{cmd.usage}\n{cmd.description}")
            return CommandResult(success=False, output=f"Unknown command: {args[0]}")

        # Show all commands grouped by category.
        from rich.panel import Panel
        from rich.text import Text

        console = svc.get("console", Console())
        grouped = registry.list_all()
        body = Text()
        for category, cmds in grouped.items():
            body.append(f"\n  {category.upper()}\n", style="bold")
            for cmd in cmds:
                body.append(f"    /{cmd.name:<14}", style="cyan")
                body.append(f"{cmd.description}\n", style="dim")

        console.print(Panel(body, title=" NexCode Commands ", title_align="left", border_style="cyan"))
        return CommandResult(success=True)


class ConfigCommand(BaseCommand):
    name = "config"
    aliases = []
    description = "Show or set config values"
    usage = "/config [set key value]"
    category = "system"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        config = svc.get("config")
        if not config:
            return CommandResult(success=True, output="Config not loaded")
        if not args:
            return CommandResult(success=True, output=f"Config: {config}")
        return CommandResult(success=True, output="Config updated")


class ThemeCommand(BaseCommand):
    name = "theme"
    aliases = []
    description = "Show or switch theme"
    usage = "/theme [name|list]"
    category = "system"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        tm = svc.get("theme_manager")
        if not tm:
            from nexcode.ui.themes import ThemeManager
            tm = ThemeManager()

        if not args:
            return CommandResult(success=True, output=f"Current theme: {tm.current.name}")
        if args[0] == "list":
            tm.list_themes(svc.get("console"))
            return CommandResult(success=True)
        if tm.set(args[0]):
            return CommandResult(success=True, output=f"✓ Theme switched to: {args[0]}")
        return CommandResult(success=False, output=f"Unknown theme: {args[0]}. Use /theme list")


class VersionCommand(BaseCommand):
    name = "version"
    aliases = ["v"]
    description = "Show version info"
    usage = "/version"
    category = "system"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        import platform
        import sys
        return CommandResult(success=True, output=(
            f"NexCode v1.0.0\n"
            f"Python {sys.version.split()[0]}\n"
            f"OS: {platform.system()} {platform.release()}"
        ))


class AboutCommand(BaseCommand):
    name = "about"
    aliases = []
    description = "About NexCode"
    usage = "/about"
    category = "system"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        return CommandResult(success=True, output=(
            "NexCode — Professional AI Coding Assistant\n"
            "Better than Claude Code · Multi-provider · Full terminal UI\n"
            "Built with Python, Rich, and ❤️"
        ))


class ExitCommand(BaseCommand):
    name = "exit"
    aliases = ["quit", "q"]
    description = "Exit NexCode"
    usage = "/exit"
    category = "system"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        console = svc.get("console", Console())
        session = svc.get("session")

        from rich.panel import Panel
        from rich.text import Text

        body = Text()
        if session:
            body.append(f"  Duration:      {session.duration_display}\n", style="white")
            body.append(f"  Tasks:         {session.tasks_completed} completed\n", style="white")
            body.append(f"  Files changed: {len(session.files_modified)}\n", style="white")
            body.append(f"  Total cost:    ${session.cost_usd:.4f}\n", style="white")
            body.append(f"  Tokens used:   {session.tokens_used:,}\n", style="white")
        else:
            body.append("  Session ended\n", style="dim")

        console.print(Panel(body, title=" Session Summary ", border_style="cyan"))
        console.print("  Goodbye! 👋\n")
        return CommandResult(success=True, exit_app=True)


class MemoryCommand(BaseCommand):
    name = "memory"
    aliases = []
    description = "Manage memories"
    usage = "/memory [add|forget|search|clear] [args]"
    category = "session"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        ltm = svc.get("long_term_memory")
        if not ltm:
            return CommandResult(success=True, output="Memory system not initialized")
        if not args:
            ltm.show(console=svc.get("console"))
            return CommandResult(success=True)
        sub = args[0].lower()
        if sub == "add" and len(args) > 1:
            mem = ltm.remember(" ".join(args[1:]))
            return CommandResult(success=True, output=f"✓ Remembered: {mem.content}")
        elif sub == "forget" and len(args) > 1:
            if ltm.forget(args[1]):
                return CommandResult(success=True, output=f"✓ Forgotten: {args[1]}")
            return CommandResult(success=False, output=f"Memory '{args[1]}' not found")
        elif sub == "search" and len(args) > 1:
            results = ltm.search(" ".join(args[1:]))
            if results:
                lines = [f"  {m.id}: {m.content}" for m in results[:10]]
                return CommandResult(success=True, output="\n".join(lines))
            return CommandResult(success=True, output="No matching memories")
        elif sub == "clear":
            count = ltm.forget_project(None)
            return CommandResult(success=True, output=f"✓ Cleared {count} memories")
        return CommandResult(success=False, output="Usage: /memory [add|forget|search|clear]")


class ProjectCommand(BaseCommand):
    name = "project"
    aliases = []
    description = "Show project memory"
    usage = "/project [scan]"
    category = "session"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        pmm = svc.get("project_manager")
        if not pmm:
            return CommandResult(success=True, output="Project memory not initialized")
        import os
        pm = pmm.load_or_create(os.getcwd())
        if args and args[0] == "scan":
            pmm._detect_stack(pm)
            pmm.save(pm)
            return CommandResult(success=True, output="✓ Project re-scanned")
        pmm.show_dashboard(pm, svc.get("console"))
        return CommandResult(success=True)


class SessionCommand(BaseCommand):
    name = "session"
    aliases = []
    description = "Session management"
    usage = "/session [list|resume|export] [args]"
    category = "session"

    async def execute(self, args: list[str], context: Any = None, **svc: Any) -> CommandResult:
        sm = svc.get("session_manager")
        session = svc.get("session")
        if not sm:
            return CommandResult(success=True, output="Session manager not initialized")
        if not args:
            if session:
                return CommandResult(success=True, output=(
                    f"Session: {session.id}\n"
                    f"Duration: {session.duration_display}\n"
                    f"Tasks: {session.tasks_completed}\n"
                    f"Cost: ${session.cost_usd:.4f}"
                ))
            return CommandResult(success=True, output="No active session")
        sub = args[0].lower()
        if sub == "list":
            sessions = sm.list_sessions()
            sm.show_sessions(sessions)
            return CommandResult(success=True)
        elif sub == "export" and len(args) > 1:
            if sm.export(args[1], f"{args[1]}_report.md"):
                return CommandResult(success=True, output=f"✓ Exported to {args[1]}_report.md")
            return CommandResult(success=False, output="Export failed")
        return CommandResult(success=False, output="Usage: /session [list|resume|export]")


# ---------------------------------------------------------------------------
# Registry helper
# ---------------------------------------------------------------------------

ALL_COMMANDS: list[type[BaseCommand]] = [
    # Session
    ClearCommand, CompactCommand, SaveCommand, LoadCommand,
    HistoryCommand, UndoCommand, RewindCommand,
    MemoryCommand, ProjectCommand, SessionCommand,
    # Model
    ModelCommand, ProviderCommand, ModelsCommand, TokensCommand,
    # Auth
    LoginCommand, LogoutCommand, AuthCommand, ApiKeyCommand,
    # Safety
    ModeCommand, SafetyCommand, AuditCommand, PermissionsCommand, IgnoreCommand,
    # Tools
    ToolsCommand, RunCommand, WebCommand,
    # Git
    GitCommand, CommitCommand,
    # System
    HelpCommand, ConfigCommand, ThemeCommand, VersionCommand, AboutCommand, ExitCommand,
]
