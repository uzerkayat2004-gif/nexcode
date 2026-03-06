"""
NexCode Git Tools
~~~~~~~~~~~~~~~~~~

Fourteen git tools for AI-driven repository management:
status, diff, stage, unstage, commit (with AI message gen),
push, pull, log, branch, stash, reset, restore, tag, blame.
"""

from __future__ import annotations

import os
from typing import Any

from nexcode.git.engine import GitEngine, GitError
from nexcode.git.diff import DiffDisplay
from nexcode.git.history import CommitHistory
from nexcode.tools.base import BaseTool, ToolResult


# ---------------------------------------------------------------------------
# Shared lazy-init
# ---------------------------------------------------------------------------

_engine: GitEngine | None = None
_diff_display: DiffDisplay | None = None
_history: CommitHistory | None = None


def _get_engine() -> GitEngine:
    global _engine
    if _engine is None:
        _engine = GitEngine()
    return _engine


def _get_diff_display() -> DiffDisplay:
    global _diff_display
    if _diff_display is None:
        _diff_display = DiffDisplay()
    return _diff_display


def _get_history() -> CommitHistory:
    global _history
    if _history is None:
        _history = CommitHistory(engine=_get_engine())
    return _history


# ═══════════════════════════════════════════════════════════════════════════
# 1. GitStatusTool ⭐
# ═══════════════════════════════════════════════════════════════════════════

class GitStatusTool(BaseTool):
    """Show full repository status."""

    name = "git_status"
    description = (
        "Show full git repository status: branch, staged/unstaged/untracked "
        "files, ahead/behind remote, stash count, and conflict status."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        engine = _get_engine()
        if not engine.is_git_repo():
            return ToolResult.fail("Not a git repository.")

        try:
            status = engine.get_status()
        except GitError as exc:
            return ToolResult.fail(str(exc))

        lines = [f"Branch: {status.branch}"]
        if status.detached:
            lines[0] += " (detached HEAD)"
        if status.ahead_commits:
            lines.append(f"↑ {status.ahead_commits} ahead of remote")
        if status.behind_commits:
            lines.append(f"↓ {status.behind_commits} behind remote")
        if status.has_conflicts:
            lines.append("⚠️  Merge conflicts detected")

        if status.staged_files:
            lines.append(f"\nStaged ({len(status.staged_files)}):")
            for f in status.staged_files:
                lines.append(f"  ✅ {f}")

        if status.unstaged_files:
            lines.append(f"\nUnstaged ({len(status.unstaged_files)}):")
            for f in status.unstaged_files:
                lines.append(f"  📝 {f}")

        if status.untracked_files:
            lines.append(f"\nUntracked ({len(status.untracked_files)}):")
            for f in status.untracked_files:
                lines.append(f"  ❓ {f}")

        if status.stash_count:
            lines.append(f"\n📦 {status.stash_count} stash(es)")

        if not status.is_dirty:
            lines.append("\n✨ Working tree clean")

        output = "\n".join(lines)
        display = f"🌿 {status.branch}"
        if status.ahead_commits:
            display += f" ↑{status.ahead_commits}"
        if status.total_changes:
            display += f" ({status.total_changes} changes)"

        return ToolResult.ok(output=output, display=display)


# ═══════════════════════════════════════════════════════════════════════════
# 2. GitDiffTool ⭐
# ═══════════════════════════════════════════════════════════════════════════

class GitDiffTool(BaseTool):
    """Show diff of changes."""

    name = "git_diff"
    description = (
        "Show colored diff of changes. Can diff staged changes, "
        "unstaged changes, specific files, or a specific commit."
    )
    parameters = {
        "type": "object",
        "properties": {
            "staged": {"type": "boolean", "description": "Show staged changes only (default: false)."},
            "path": {"type": "string", "description": "Diff a specific file only."},
            "commit": {"type": "string", "description": "Show diff for a specific commit hash."},
        },
        "required": [],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        engine = _get_engine()
        try:
            diff_text = engine.get_diff(
                staged=kwargs.get("staged", False),
                path=kwargs.get("path"),
                commit=kwargs.get("commit"),
            )
        except GitError as exc:
            return ToolResult.fail(str(exc))

        if not diff_text.strip():
            return ToolResult.ok(output="No changes.", display="No changes")

        dd = _get_diff_display()
        summary = dd.format_summary_text(diff_text)

        return ToolResult.ok(
            output=f"{summary}\n\n{diff_text}",
            display=f"Diff: {summary}",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. GitStageTool
# ═══════════════════════════════════════════════════════════════════════════

class GitStageTool(BaseTool):
    """Stage files for commit."""

    name = "git_stage"
    description = "Stage files for commit. Use '*' to stage all changes."
    parameters = {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to stage. Use ['*'] to stage all.",
            },
        },
        "required": ["paths"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        paths: list[str] = kwargs["paths"]
        engine = _get_engine()
        try:
            engine.stage(paths)
            if paths == ["*"]:
                return ToolResult.ok(output="Staged all changes.", display="✅ Staged all")
            return ToolResult.ok(
                output=f"Staged: {', '.join(paths)}",
                display=f"✅ Staged {len(paths)} file(s)",
            )
        except GitError as exc:
            return ToolResult.fail(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# 4. GitUnstageTool
# ═══════════════════════════════════════════════════════════════════════════

class GitUnstageTool(BaseTool):
    """Unstage files."""

    name = "git_unstage"
    description = "Unstage files. Use '*' to unstage all."
    parameters = {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to unstage. Use ['*'] to unstage all.",
            },
        },
        "required": ["paths"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        paths: list[str] = kwargs["paths"]
        engine = _get_engine()
        try:
            engine.unstage(paths)
            return ToolResult.ok(
                output=f"Unstaged: {', '.join(paths)}",
                display=f"↩ Unstaged {len(paths)} file(s)",
            )
        except GitError as exc:
            return ToolResult.fail(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# 5. GitCommitTool ⭐
# ═══════════════════════════════════════════════════════════════════════════

class GitCommitTool(BaseTool):
    """Commit staged changes with optional AI-generated message."""

    name = "git_commit"
    description = (
        "Commit staged changes. If no message is provided, the AI will "
        "analyze the diff and generate a conventional commit message."
    )
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Commit message. If empty, AI generates one."},
            "amend": {"type": "boolean", "description": "Amend the last commit (default: false)."},
        },
        "required": [],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        message: str = kwargs.get("message", "")
        amend: bool = kwargs.get("amend", False)
        engine = _get_engine()

        # Generate message from diff if not provided.
        if not message:
            try:
                diff = engine.get_diff(staged=True)
                status = engine.get_status()
                message = _auto_commit_message(diff, status.staged_files)
            except Exception:
                message = "chore: update files"

        try:
            info = engine.commit(message, amend=amend)
            action = "Amended" if amend else "Committed"
            return ToolResult.ok(
                output=(
                    f"{action}: {info.short_hash} {info.message}\n"
                    f"Author: {info.author}\n"
                    f"Files: {info.files_changed}, +{info.insertions} -{info.deletions}"
                ),
                display=f"💾 {info.short_hash} {info.message}",
            )
        except GitError as exc:
            return ToolResult.fail(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# 6. GitPushTool
# ═══════════════════════════════════════════════════════════════════════════

class GitPushTool(BaseTool):
    """Push commits to remote."""

    name = "git_push"
    description = "Push commits to remote repository."
    parameters = {
        "type": "object",
        "properties": {
            "remote": {"type": "string", "description": "Remote name (default: origin)."},
            "branch": {"type": "string", "description": "Branch to push (default: current)."},
            "force": {"type": "boolean", "description": "Force push (default: false)."},
        },
        "required": [],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        engine = _get_engine()
        remote = kwargs.get("remote", "origin")
        branch = kwargs.get("branch")
        force = kwargs.get("force", False)

        try:
            await engine.push(remote=remote, branch=branch, force=force)
            branch_name = branch or engine.get_current_branch()
            action = "Force pushed" if force else "Pushed"
            return ToolResult.ok(
                output=f"{action} to {remote}/{branch_name}",
                display=f"🚀 {action} to {remote}/{branch_name}",
            )
        except GitError as exc:
            return ToolResult.fail(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# 7. GitPullTool
# ═══════════════════════════════════════════════════════════════════════════

class GitPullTool(BaseTool):
    """Pull from remote."""

    name = "git_pull"
    description = "Pull changes from remote repository."
    parameters = {
        "type": "object",
        "properties": {
            "remote": {"type": "string", "description": "Remote name (default: origin)."},
            "branch": {"type": "string", "description": "Branch to pull."},
            "rebase": {"type": "boolean", "description": "Pull with rebase (default: false)."},
        },
        "required": [],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        engine = _get_engine()
        try:
            await engine.pull(
                remote=kwargs.get("remote", "origin"),
                branch=kwargs.get("branch"),
                rebase=kwargs.get("rebase", False),
            )
            mode = " (rebase)" if kwargs.get("rebase") else ""
            return ToolResult.ok(
                output=f"Pulled from remote{mode}",
                display=f"⬇ Pulled{mode}",
            )
        except GitError as exc:
            return ToolResult.fail(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# 8. GitLogTool
# ═══════════════════════════════════════════════════════════════════════════

class GitLogTool(BaseTool):
    """Show commit history."""

    name = "git_log"
    description = "Show commit history with author, date, and stats."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max commits to show (default: 20)."},
            "path": {"type": "string", "description": "Show commits for a specific file."},
            "branch": {"type": "string", "description": "Branch to show log for."},
        },
        "required": [],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        engine = _get_engine()
        try:
            commits = engine.get_log(
                limit=kwargs.get("limit", 20),
                path=kwargs.get("path"),
                branch=kwargs.get("branch"),
            )
        except GitError as exc:
            return ToolResult.fail(str(exc))

        history = _get_history()
        output = history.show_log(commits, show_graph=True)
        return ToolResult.ok(
            output=output,
            display=f"📜 {len(commits)} commits",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 9. GitBranchTool
# ═══════════════════════════════════════════════════════════════════════════

class GitBranchTool(BaseTool):
    """Full branch management."""

    name = "git_branch"
    description = (
        "Branch management. Actions: list, create, checkout, delete, merge."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "checkout", "delete", "merge"],
                "description": "Branch action to perform.",
            },
            "name": {"type": "string", "description": "Branch name (for create/checkout/delete/merge)."},
            "force": {"type": "boolean", "description": "Force delete (default: false)."},
        },
        "required": ["action"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        action: str = kwargs["action"]
        name: str = kwargs.get("name", "")
        force: bool = kwargs.get("force", False)
        engine = _get_engine()

        try:
            if action == "list":
                branches = engine.list_branches()
                current = engine.get_current_branch()
                lines = [f"Current: {current}\n"]
                lines.append("Local:")
                for b in branches["local"]:
                    marker = " * " if b == current else "   "
                    lines.append(f"{marker}{b}")
                if branches["remote"]:
                    lines.append("\nRemote:")
                    for b in branches["remote"]:
                        lines.append(f"   {b}")
                return ToolResult.ok(output="\n".join(lines), display=f"🌿 {len(branches['local'])} branches")

            elif action == "create":
                if not name:
                    return ToolResult.fail("Branch name required for 'create'.")
                engine.create_branch(name, checkout=True)
                return ToolResult.ok(output=f"Created and switched to '{name}'", display=f"🌿 Created {name}")

            elif action == "checkout":
                if not name:
                    return ToolResult.fail("Branch name required for 'checkout'.")
                engine.checkout_branch(name)
                return ToolResult.ok(output=f"Switched to '{name}'", display=f"🔀 Switched to {name}")

            elif action == "delete":
                if not name:
                    return ToolResult.fail("Branch name required for 'delete'.")
                engine.delete_branch(name, force=force)
                return ToolResult.ok(output=f"Deleted branch '{name}'", display=f"🗑 Deleted {name}")

            elif action == "merge":
                if not name:
                    return ToolResult.fail("Branch name required for 'merge'.")
                engine.merge_branch(name)
                return ToolResult.ok(output=f"Merged '{name}' into current branch", display=f"🔀 Merged {name}")

            else:
                return ToolResult.fail(f"Unknown branch action: {action}")

        except GitError as exc:
            return ToolResult.fail(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# 10. GitStashTool
# ═══════════════════════════════════════════════════════════════════════════

class GitStashTool(BaseTool):
    """Stash management."""

    name = "git_stash"
    description = "Stash management. Actions: save, pop, list, drop."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["save", "pop", "list"],
                "description": "Stash action.",
            },
            "message": {"type": "string", "description": "Stash message (for save)."},
            "index": {"type": "integer", "description": "Stash index (for pop, default: 0)."},
        },
        "required": ["action"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        action: str = kwargs["action"]
        engine = _get_engine()

        try:
            if action == "save":
                engine.stash_save(message=kwargs.get("message"))
                return ToolResult.ok(output="Changes stashed.", display="📦 Stashed")

            elif action == "pop":
                engine.stash_pop(index=kwargs.get("index", 0))
                return ToolResult.ok(output="Stash popped.", display="📦 Popped stash")

            elif action == "list":
                entries = engine.stash_list()
                if not entries:
                    return ToolResult.ok(output="No stashes.", display="No stashes")
                lines = [f"{e['index']}: {e['message']}" for e in entries]
                return ToolResult.ok(output="\n".join(lines), display=f"📦 {len(entries)} stash(es)")

            else:
                return ToolResult.fail(f"Unknown stash action: {action}")

        except GitError as exc:
            return ToolResult.fail(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# 11. GitResetTool
# ═══════════════════════════════════════════════════════════════════════════

class GitResetTool(BaseTool):
    """Reset commits or discard changes."""

    name = "git_reset"
    description = (
        "Reset commits. Modes: 'soft' (keep changes staged), "
        "'hard' (discard all changes — dangerous!)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["soft", "hard"],
                "description": "Reset mode.",
            },
            "commit": {"type": "string", "description": "Target commit (default: HEAD~1 for soft, HEAD for hard)."},
        },
        "required": ["mode"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        mode: str = kwargs["mode"]
        engine = _get_engine()

        try:
            if mode == "soft":
                commit = kwargs.get("commit", "HEAD~1")
                engine.reset_soft(commit)
                return ToolResult.ok(output=f"Soft reset to {commit}", display=f"↩ Soft reset to {commit}")

            elif mode == "hard":
                commit = kwargs.get("commit", "HEAD")
                engine.reset_hard(commit)
                return ToolResult.ok(
                    output=f"Hard reset to {commit} — all uncommitted changes discarded",
                    display=f"⚠️ Hard reset to {commit}",
                )

            else:
                return ToolResult.fail(f"Unknown reset mode: {mode}")

        except GitError as exc:
            return ToolResult.fail(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# 12. GitRestoreFileTool
# ═══════════════════════════════════════════════════════════════════════════

class GitRestoreFileTool(BaseTool):
    """Discard uncommitted changes in a file."""

    name = "git_restore"
    description = "Discard all uncommitted changes in a specific file."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File to restore."},
        },
        "required": ["path"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        path: str = kwargs["path"]
        engine = _get_engine()
        try:
            engine.restore_file(path)
            return ToolResult.ok(output=f"Restored {path}", display=f"↩ Restored {path}")
        except GitError as exc:
            return ToolResult.fail(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# 13. GitCreateTagTool
# ═══════════════════════════════════════════════════════════════════════════

class GitCreateTagTool(BaseTool):
    """Create a git tag."""

    name = "git_tag"
    description = "Create a git tag. Optionally push it to remote."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Tag name (e.g., 'v1.0.0')."},
            "message": {"type": "string", "description": "Tag message (creates annotated tag)."},
            "push": {"type": "boolean", "description": "Push tag to remote (default: false)."},
        },
        "required": ["name"],
    }
    is_destructive = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        tag_name: str = kwargs["name"]
        message: str | None = kwargs.get("message")
        push: bool = kwargs.get("push", False)
        engine = _get_engine()

        try:
            engine.create_tag(tag_name, message=message)
            result = f"Created tag '{tag_name}'"
            if push:
                engine.push_tags()
                result += " and pushed to remote"
            return ToolResult.ok(output=result, display=f"🏷 {tag_name}")
        except GitError as exc:
            return ToolResult.fail(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# 14. GitBlameTool
# ═══════════════════════════════════════════════════════════════════════════

class GitBlameTool(BaseTool):
    """Show who last modified each line of a file."""

    name = "git_blame"
    description = "Show git blame for a file — who last modified each line."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File to blame."},
            "start_line": {"type": "integer", "description": "Start line (optional)."},
            "end_line": {"type": "integer", "description": "End line (optional)."},
        },
        "required": ["path"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> ToolResult:
        path: str = kwargs["path"]
        engine = _get_engine()
        try:
            output = engine.blame(
                path,
                start_line=kwargs.get("start_line"),
                end_line=kwargs.get("end_line"),
            )
            if not output.strip():
                return ToolResult.ok(output="No blame data.", display="No blame data")
            return ToolResult.ok(output=output, display=f"Blame: {path}")
        except GitError as exc:
            return ToolResult.fail(str(exc))


# ---------------------------------------------------------------------------
# Auto commit message generator
# ---------------------------------------------------------------------------

def _auto_commit_message(diff: str, staged_files: list[str]) -> str:
    """
    Generate a conventional commit message from a diff.

    This is a heuristic-based fallback — when the AI provider is
    available, the full CommitMessageGenerator uses the LLM instead.
    """
    if not staged_files:
        return "chore: update files"

    # Determine commit type from file patterns.
    all_files = " ".join(staged_files).lower()

    if any(f.startswith("test") or "test_" in f or "_test." in f for f in staged_files):
        commit_type = "test"
    elif any(f.endswith((".md", ".txt", ".rst")) for f in staged_files):
        commit_type = "docs"
    elif any(f.endswith((".css", ".scss", ".less")) for f in staged_files):
        commit_type = "style"
    elif len(staged_files) == 1 and staged_files[0] in (
        "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
        "requirements.txt", ".gitignore",
    ):
        commit_type = "chore"
    elif "+def " in diff or "+class " in diff or "+function " in diff:
        commit_type = "feat"
    elif "-def " in diff or "-class " in diff:
        commit_type = "refactor"
    else:
        # Count additions vs deletions as a heuristic.
        additions = diff.count("\n+") - diff.count("\n+++")
        deletions = diff.count("\n-") - diff.count("\n---")
        if additions > deletions * 2:
            commit_type = "feat"
        elif deletions > additions * 2:
            commit_type = "refactor"
        else:
            commit_type = "fix"

    # Determine scope from file paths.
    scope = ""
    if len(staged_files) == 1:
        parts = staged_files[0].replace("\\", "/").split("/")
        if len(parts) > 1:
            scope = parts[-2]  # parent directory name
    elif len(staged_files) <= 5:
        # Find common parent.
        common_parts = staged_files[0].replace("\\", "/").split("/")
        for f in staged_files[1:]:
            f_parts = f.replace("\\", "/").split("/")
            common_parts = [
                a for a, b in zip(common_parts, f_parts) if a == b
            ]
        if common_parts:
            scope = common_parts[-1]

    # Build message.
    file_count = len(staged_files)
    if file_count == 1:
        desc = f"update {staged_files[0].split('/')[-1]}"
    else:
        desc = f"update {file_count} files"

    if scope:
        return f"{commit_type}({scope}): {desc}"
    else:
        return f"{commit_type}: {desc}"
