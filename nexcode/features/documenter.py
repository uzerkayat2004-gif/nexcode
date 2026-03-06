"""
NexCode Auto Documentation Generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generates project docs, docstrings, README, and API reference.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console


@dataclass
class DocumentationResult:
    files_documented: int = 0
    output_path: str = ""
    format: str = "markdown"
    content: str = ""


@dataclass
class DocstringResult:
    files_modified: int = 0
    docstrings_added: int = 0
    functions_skipped: int = 0


@dataclass
class OutdatedDoc:
    doc_file: str = ""
    source_file: str = ""
    reason: str = ""


@dataclass
class SyncResult:
    docs_updated: int = 0
    docs_created: int = 0


class AutoDocumenter:
    """AI-powered documentation generator."""

    def __init__(self, ai_provider: Any = None, console: Console | None = None) -> None:
        self.ai = ai_provider
        self.console = console or Console()

    async def document_project(
        self,
        output_format: str = "markdown",
        style: str = "comprehensive",
    ) -> DocumentationResult:
        """Generate docs for entire project."""
        files = self._collect_source_files()
        sections: list[str] = ["# Project Documentation\n"]

        for fpath in files[:30]:
            doc = await self.document_file(fpath, output_format)
            if doc:
                sections.append(doc)

        content = "\n\n---\n\n".join(sections)
        out_path = os.path.join(os.getcwd(), "docs", "API.md")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(content, encoding="utf-8")

        return DocumentationResult(files_documented=len(files), output_path=out_path, content=content)

    async def document_file(self, path: str, output_format: str = "markdown") -> str:
        """Generate docs for a single file."""
        try:
            content = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

        if not self.ai:
            return f"## {os.path.basename(path)}\n\n```\n{content[:500]}\n```"

        try:
            resp = await self.ai.chat(
                messages=[{"role": "user", "content": f"Generate {output_format} documentation for:\n\n{content[:6000]}"}],
                system="You generate clear, comprehensive documentation in the requested format.",
            )
            return getattr(resp, "content", str(resp))
        except Exception:
            return f"## {os.path.basename(path)}\n\n(Documentation generation failed)"

    async def add_docstrings(
        self,
        paths: list[str] | None = None,
        style: str = "google",
    ) -> DocstringResult:
        """Add docstrings to undocumented functions."""
        files = paths or self._collect_source_files(".py")
        result = DocstringResult()

        for fpath in files[:20]:
            try:
                content = Path(fpath).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if not self.ai:
                continue

            try:
                resp = await self.ai.chat(
                    messages=[{"role": "user", "content": (
                        f"Add {style}-style docstrings to all undocumented functions and classes.\n"
                        f"Return the COMPLETE updated file.\n\n{content[:6000]}"
                    )}],
                    system="You add docstrings. Return only the complete updated code, no explanations.",
                )
                new_content = getattr(resp, "content", "")
                if new_content and len(new_content) > len(content) * 0.8:
                    Path(fpath).write_text(new_content, encoding="utf-8")
                    result.files_modified += 1
                    result.docstrings_added += new_content.count('"""') - content.count('"""')
            except Exception:
                result.functions_skipped += 1

        return result

    async def generate_readme(self) -> str:
        """Generate README.md from project analysis."""
        project_name = os.path.basename(os.getcwd())
        files = self._collect_source_files()

        context = f"Project: {project_name}\nFiles: {len(files)}\n"
        for f in files[:10]:
            context += f"  - {os.path.relpath(f)}\n"

        # Check for package files.
        for pkg_file in ["pyproject.toml", "package.json", "Cargo.toml", "go.mod"]:
            pkg_path = os.path.join(os.getcwd(), pkg_file)
            if os.path.exists(pkg_path):
                try:
                    context += f"\n{pkg_file}:\n{Path(pkg_path).read_text(encoding='utf-8')[:1000]}\n"
                except OSError:
                    pass

        if not self.ai:
            return f"# {project_name}\n\nProject documentation."

        try:
            resp = await self.ai.chat(
                messages=[{"role": "user", "content": f"Generate a professional README.md:\n\n{context}"}],
                system="Generate a complete, professional README.md with sections for description, features, installation, usage, and license.",
            )
            readme = getattr(resp, "content", f"# {project_name}")
            Path(os.path.join(os.getcwd(), "README.md")).write_text(readme, encoding="utf-8")
            return readme
        except Exception:
            return f"# {project_name}"

    async def generate_api_docs(self, output_dir: str = "docs/") -> None:
        """Generate API reference."""
        await self.document_project(output_format="markdown", style="api-only")

    async def check_sync(self) -> list[OutdatedDoc]:
        """Detect outdated docs."""
        outdated: list[OutdatedDoc] = []
        docs_dir = os.path.join(os.getcwd(), "docs")
        if not os.path.exists(docs_dir):
            return outdated
        for doc_file in Path(docs_dir).glob("**/*.md"):
            stat = doc_file.stat()
            # Simple heuristic: if doc is older than 30 days, flag it.
            import time
            if time.time() - stat.st_mtime > 30 * 86400:
                outdated.append(OutdatedDoc(doc_file=str(doc_file), reason="Older than 30 days"))
        return outdated

    async def sync_docs(self) -> SyncResult:
        """Update outdated docs."""
        outdated = await self.check_sync()
        result = SyncResult()
        for doc in outdated:
            new_content = await self.document_file(doc.doc_file)
            if new_content:
                Path(doc.doc_file).write_text(new_content, encoding="utf-8")
                result.docs_updated += 1
        return result

    async def generate_changelog_entry(self) -> str:
        """Generate CHANGELOG entry from recent commits."""
        try:
            from nexcode.features.changelog import ChangelogGenerator
            gen = ChangelogGenerator(self.ai)
            return await gen.generate_next_entry("next")
        except Exception:
            return ""

    def _collect_source_files(self, ext_filter: str | None = None) -> list[str]:
        exts = {ext_filter} if ext_filter else {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs"}
        result: list[str] = []
        for root, _, files in os.walk(os.getcwd()):
            if any(d in root for d in [".git", "node_modules", "__pycache__", ".venv"]):
                continue
            for f in files:
                if Path(f).suffix in exts:
                    result.append(os.path.join(root, f))
        return result[:50]
