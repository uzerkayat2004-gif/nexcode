"""
NexCode Git Engine
~~~~~~~~~~~~~~~~~~~

Core Git operations powered by GitPython.  Provides a high-level,
exception-safe API for status, staging, committing, branching,
stashing, tagging, and remote operations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GitStatus:
    """Snapshot of the repository state."""

    branch: str
    is_dirty: bool
    staged_files: list[str]
    unstaged_files: list[str]
    untracked_files: list[str]
    ahead_commits: int = 0
    behind_commits: int = 0
    has_conflicts: bool = False
    stash_count: int = 0
    detached: bool = False

    @property
    def total_changes(self) -> int:
        return len(self.staged_files) + len(self.unstaged_files) + len(self.untracked_files)


@dataclass
class CommitInfo:
    """Metadata for a single commit."""

    hash: str
    short_hash: str
    message: str
    author: str
    email: str
    date: datetime
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


# ---------------------------------------------------------------------------
# GitEngine
# ---------------------------------------------------------------------------

class GitEngine:
    """
    High-level Git operations engine backed by GitPython.

    All methods are safe to call even on non-git directories —
    they return sensible defaults or raise ``GitError``.
    """

    def __init__(self, cwd: str | None = None) -> None:
        self._cwd = cwd or os.getcwd()
        self._repo: Any = None  # git.Repo instance, lazy-loaded

    # ── Repo access ────────────────────────────────────────────────────────

    def _get_repo(self) -> Any:
        """Lazy-load the git.Repo object."""
        if self._repo is None:
            try:
                import git
            except ImportError:
                raise GitError(
                    "gitpython is not installed. Run: uv add gitpython"
                )
            try:
                self._repo = git.Repo(self._cwd, search_parent_directories=True)
            except git.InvalidGitRepositoryError:
                raise GitError("Not a git repository.")
            except git.NoSuchPathError:
                raise GitError(f"Path not found: {self._cwd}")
        return self._repo

    def is_git_repo(self) -> bool:
        try:
            self._get_repo()
            return True
        except GitError:
            return False

    def init(self) -> bool:
        """Initialize a new git repository."""
        try:
            import git
        except ImportError:
            raise GitError("gitpython is not installed. Run: uv add gitpython")
        try:
            self._repo = git.Repo.init(self._cwd)
            return True
        except Exception as exc:
            raise GitError(f"Failed to initialize repo: {exc}") from exc

    # ── Status ─────────────────────────────────────────────────────────────

    def get_status(self) -> GitStatus:
        """Get full repository status."""
        repo = self._get_repo()

        # Current branch.
        try:
            branch = repo.active_branch.name
            detached = False
        except TypeError:
            branch = str(repo.head.commit)[:7]
            detached = True

        # Staged files.
        staged = [d.a_path for d in repo.index.diff("HEAD")] if repo.head.is_valid() else []

        # Unstaged files.
        unstaged = [d.a_path for d in repo.index.diff(None)]

        # Untracked.
        untracked = repo.untracked_files

        # Ahead/behind remote.
        ahead, behind = 0, 0
        try:
            if not detached:
                tracking = repo.active_branch.tracking_branch()
                if tracking:
                    commits_behind = list(repo.iter_commits(f"{branch}..{tracking.name}"))
                    commits_ahead = list(repo.iter_commits(f"{tracking.name}..{branch}"))
                    ahead = len(commits_ahead)
                    behind = len(commits_behind)
        except Exception:
            pass

        # Conflicts.
        has_conflicts = bool(repo.index.unmerged_blobs())

        # Stash count.
        stash_count = 0
        try:
            stash_count = len(list(repo.iter_commits("refs/stash")))
        except Exception:
            pass

        return GitStatus(
            branch=branch,
            is_dirty=repo.is_dirty(untracked_files=True),
            staged_files=staged,
            unstaged_files=unstaged,
            untracked_files=list(untracked),
            ahead_commits=ahead,
            behind_commits=behind,
            has_conflicts=has_conflicts,
            stash_count=stash_count,
            detached=detached,
        )

    # ── Staging ────────────────────────────────────────────────────────────

    def stage(self, paths: list[str] | str) -> bool:
        """Stage files for commit."""
        repo = self._get_repo()
        if isinstance(paths, str):
            paths = [paths]
        if paths == ["*"] or paths == ["."]:
            repo.git.add(A=True)
        else:
            repo.index.add(paths)
        return True

    def unstage(self, paths: list[str] | str) -> bool:
        """Unstage files."""
        repo = self._get_repo()
        if isinstance(paths, str):
            paths = [paths]
        if paths == ["*"] or paths == ["."]:
            repo.git.reset("HEAD")
        else:
            repo.index.reset(paths=paths)
        return True

    # ── Commit ─────────────────────────────────────────────────────────────

    def commit(self, message: str, amend: bool = False) -> CommitInfo:
        """Commit staged changes."""
        repo = self._get_repo()
        try:
            if amend:
                repo.git.commit("--amend", "-m", message)
            else:
                repo.index.commit(message)
            return self._commit_to_info(repo.head.commit)
        except Exception as exc:
            raise GitError(f"Commit failed: {exc}") from exc

    # ── Push / Pull ────────────────────────────────────────────────────────

    async def push(
        self,
        remote: str = "origin",
        branch: str | None = None,
        force: bool = False,
    ) -> bool:
        """Push to remote."""
        repo = self._get_repo()
        try:
            remote_obj = repo.remote(remote)
            args = []
            if force:
                args.append("--force")
            refspec = branch or repo.active_branch.name
            remote_obj.push(refspec, *args)
            return True
        except Exception as exc:
            raise GitError(f"Push failed: {exc}") from exc

    async def pull(
        self,
        remote: str = "origin",
        branch: str | None = None,
        rebase: bool = False,
    ) -> bool:
        """Pull from remote."""
        repo = self._get_repo()
        try:
            remote_obj = repo.remote(remote)
            args = []
            if rebase:
                args.append("--rebase")
            remote_obj.pull(branch, *args)
            return True
        except Exception as exc:
            raise GitError(f"Pull failed: {exc}") from exc

    # ── Diff ───────────────────────────────────────────────────────────────

    def get_diff(
        self,
        staged: bool = False,
        path: str | None = None,
        commit: str | None = None,
    ) -> str:
        """Get diff as raw text."""
        repo = self._get_repo()
        try:
            if commit:
                c = repo.commit(commit)
                diff_text = repo.git.diff(f"{c.hexsha}~1", c.hexsha)
            elif staged:
                diff_text = repo.git.diff("--cached")
            else:
                diff_text = repo.git.diff()

            if path:
                # Re-run with path filter.
                if commit:
                    c = repo.commit(commit)
                    diff_text = repo.git.diff(f"{c.hexsha}~1", c.hexsha, "--", path)
                elif staged:
                    diff_text = repo.git.diff("--cached", "--", path)
                else:
                    diff_text = repo.git.diff("--", path)

            return diff_text
        except Exception as exc:
            raise GitError(f"Diff failed: {exc}") from exc

    # ── Log ────────────────────────────────────────────────────────────────

    def get_log(
        self,
        limit: int = 20,
        path: str | None = None,
        branch: str | None = None,
    ) -> list[CommitInfo]:
        """Get commit history."""
        repo = self._get_repo()
        try:
            kwargs: dict[str, Any] = {"max_count": limit}
            if path:
                kwargs["paths"] = path
            rev = branch or repo.active_branch.name if not repo.head.is_detached else "HEAD"
            commits = list(repo.iter_commits(rev, **kwargs))
            return [self._commit_to_info(c) for c in commits]
        except Exception as exc:
            raise GitError(f"Log failed: {exc}") from exc

    # ── Branches ───────────────────────────────────────────────────────────

    def create_branch(self, name: str, checkout: bool = True) -> bool:
        repo = self._get_repo()
        try:
            new_branch = repo.create_head(name)
            if checkout:
                new_branch.checkout()
            return True
        except Exception as exc:
            raise GitError(f"Branch creation failed: {exc}") from exc

    def checkout_branch(self, name: str) -> bool:
        repo = self._get_repo()
        try:
            repo.git.checkout(name)
            return True
        except Exception as exc:
            raise GitError(f"Checkout failed: {exc}") from exc

    def delete_branch(self, name: str, force: bool = False) -> bool:
        repo = self._get_repo()
        try:
            flag = "-D" if force else "-d"
            repo.git.branch(flag, name)
            return True
        except Exception as exc:
            raise GitError(f"Branch deletion failed: {exc}") from exc

    def list_branches(self) -> dict[str, list[str]]:
        """Return local and remote branch names."""
        repo = self._get_repo()
        local = [b.name for b in repo.branches]
        remote = [r.name for r in repo.remote().refs] if repo.remotes else []
        return {"local": local, "remote": remote}

    def merge_branch(self, name: str) -> bool:
        repo = self._get_repo()
        try:
            repo.git.merge(name)
            return True
        except Exception as exc:
            raise GitError(f"Merge failed: {exc}") from exc

    def get_current_branch(self) -> str:
        repo = self._get_repo()
        try:
            return repo.active_branch.name
        except TypeError:
            return f"detached@{repo.head.commit.hexsha[:7]}"

    # ── Stash ──────────────────────────────────────────────────────────────

    def stash_save(self, message: str | None = None) -> bool:
        repo = self._get_repo()
        try:
            args = ["save"]
            if message:
                args.append(message)
            repo.git.stash(*args)
            return True
        except Exception as exc:
            raise GitError(f"Stash save failed: {exc}") from exc

    def stash_pop(self, index: int = 0) -> bool:
        repo = self._get_repo()
        try:
            repo.git.stash("pop", f"stash@{{{index}}}")
            return True
        except Exception as exc:
            raise GitError(f"Stash pop failed: {exc}") from exc

    def stash_list(self) -> list[dict[str, str]]:
        repo = self._get_repo()
        try:
            output = repo.git.stash("list")
            if not output.strip():
                return []
            entries: list[dict[str, str]] = []
            for line in output.strip().splitlines():
                parts = line.split(": ", 2)
                entries.append({
                    "index": parts[0] if len(parts) > 0 else "",
                    "branch": parts[1] if len(parts) > 1 else "",
                    "message": parts[2] if len(parts) > 2 else "",
                })
            return entries
        except Exception:
            return []

    # ── Remotes ────────────────────────────────────────────────────────────

    def list_remotes(self) -> list[dict[str, str]]:
        repo = self._get_repo()
        return [{"name": r.name, "url": list(r.urls)[0] if r.urls else ""} for r in repo.remotes]

    def add_remote(self, name: str, url: str) -> bool:
        repo = self._get_repo()
        try:
            repo.create_remote(name, url)
            return True
        except Exception as exc:
            raise GitError(f"Add remote failed: {exc}") from exc

    def get_remote_url(self) -> str | None:
        repo = self._get_repo()
        if repo.remotes:
            urls = list(repo.remotes[0].urls)
            return urls[0] if urls else None
        return None

    def get_repo_name(self) -> str:
        url = self.get_remote_url()
        if url:
            name = url.rstrip("/").split("/")[-1]
            return name.removesuffix(".git")
        return Path(self.get_root()).name

    # ── Reset / Restore ────────────────────────────────────────────────────

    def reset_soft(self, commit: str = "HEAD~1") -> bool:
        repo = self._get_repo()
        try:
            repo.git.reset("--soft", commit)
            return True
        except Exception as exc:
            raise GitError(f"Soft reset failed: {exc}") from exc

    def reset_hard(self, commit: str = "HEAD") -> bool:
        repo = self._get_repo()
        try:
            repo.git.reset("--hard", commit)
            return True
        except Exception as exc:
            raise GitError(f"Hard reset failed: {exc}") from exc

    def restore_file(self, path: str) -> bool:
        """Discard uncommitted changes in a specific file."""
        repo = self._get_repo()
        try:
            repo.git.checkout("--", path)
            return True
        except Exception as exc:
            raise GitError(f"Restore failed: {exc}") from exc

    # ── Tags ───────────────────────────────────────────────────────────────

    def create_tag(self, name: str, message: str | None = None) -> bool:
        repo = self._get_repo()
        try:
            if message:
                repo.create_tag(name, message=message)
            else:
                repo.create_tag(name)
            return True
        except Exception as exc:
            raise GitError(f"Tag creation failed: {exc}") from exc

    def list_tags(self) -> list[str]:
        repo = self._get_repo()
        return [t.name for t in repo.tags]

    def push_tags(self) -> bool:
        repo = self._get_repo()
        try:
            if repo.remotes:
                repo.remotes[0].push(tags=True)
            return True
        except Exception as exc:
            raise GitError(f"Push tags failed: {exc}") from exc

    # ── Blame ──────────────────────────────────────────────────────────────

    def blame(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """Git blame for a file, optionally limited to a line range."""
        repo = self._get_repo()
        try:
            args = [path]
            if start_line and end_line:
                args = ["-L", f"{start_line},{end_line}", path]
            return repo.git.blame(*args)
        except Exception as exc:
            raise GitError(f"Blame failed: {exc}") from exc

    # ── Utility ────────────────────────────────────────────────────────────

    def get_root(self) -> str:
        repo = self._get_repo()
        return repo.working_dir

    # ── Internal ───────────────────────────────────────────────────────────

    def _commit_to_info(self, commit: Any) -> CommitInfo:
        """Convert a GitPython commit to CommitInfo."""
        try:
            stats = commit.stats.total
            files_changed = stats.get("files", 0)
            insertions = stats.get("insertions", 0)
            deletions = stats.get("deletions", 0)
        except Exception:
            files_changed, insertions, deletions = 0, 0, 0

        return CommitInfo(
            hash=commit.hexsha,
            short_hash=commit.hexsha[:7],
            message=commit.message.strip(),
            author=str(commit.author),
            email=commit.author.email if commit.author else "",
            date=datetime.fromtimestamp(commit.committed_date, tz=UTC),
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions,
        )


# ---------------------------------------------------------------------------
# GitError
# ---------------------------------------------------------------------------

class GitError(Exception):
    """A git operation failed."""
    pass
