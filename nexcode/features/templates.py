"""
NexCode Project Template System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

10 built-in templates + AI-powered custom scaffolding.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


@dataclass
class TemplateFile:
    path: str = ""
    content: str = ""


@dataclass
class ProjectTemplate:
    id: str = ""
    name: str = ""
    description: str = ""
    language: str = ""
    framework: str | None = None
    files: list[TemplateFile] = field(default_factory=list)
    post_install_commands: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


BUILT_IN_TEMPLATES: list[ProjectTemplate] = [
    ProjectTemplate(
        id="python-api", name="Python FastAPI",
        description="FastAPI + SQLAlchemy + Alembic + pytest",
        language="Python", framework="FastAPI",
        files=[
            TemplateFile("app/main.py", 'from fastapi import FastAPI\n\napp = FastAPI(title="{{name}}")\n\n@app.get("/")\ndef root():\n    return {"message": "Hello from {{name}}"}\n'),
            TemplateFile("app/__init__.py", ""),
            TemplateFile("requirements.txt", "fastapi>=0.100.0\nuvicorn[standard]>=0.23.0\nsqlalchemy>=2.0\nalembic>=1.11\npytest>=7.0\nhttpx>=0.24\n"),
            TemplateFile("README.md", "# {{name}}\n\nFastAPI application.\n\n## Setup\n```bash\npip install -r requirements.txt\nuvicorn app.main:app --reload\n```\n"),
            TemplateFile(".gitignore", "__pycache__/\n.venv/\n*.pyc\n.env\n"),
        ],
        post_install_commands=["pip install -r requirements.txt"],
        tags=["api", "backend", "python"],
    ),
    ProjectTemplate(
        id="python-cli", name="Python CLI App",
        description="Click + Rich + pytest",
        language="Python", framework="Click",
        files=[
            TemplateFile("cli.py", 'import click\nfrom rich.console import Console\n\nconsole = Console()\n\n@click.command()\n@click.argument("name")\ndef main(name: str):\n    console.print(f"Hello, [bold]{name}[/]!")\n\nif __name__ == "__main__":\n    main()\n'),
            TemplateFile("requirements.txt", "click>=8.0\nrich>=13.0\npytest>=7.0\n"),
            TemplateFile("README.md", "# {{name}}\n\nCLI application.\n"),
        ],
        tags=["cli", "python"],
    ),
    ProjectTemplate(
        id="react-app", name="React + TypeScript",
        description="React + TypeScript + Tailwind + Vite",
        language="TypeScript", framework="React",
        files=[TemplateFile("README.md", "# {{name}}\n\nReact + TypeScript app.\n\n## Setup\n```bash\nnpx create-vite . --template react-ts\n```\n")],
        post_install_commands=["npx -y create-vite@latest . --template react-ts"],
        tags=["frontend", "react", "typescript"],
    ),
    ProjectTemplate(
        id="nextjs-app", name="Next.js Full-Stack",
        description="Next.js + TypeScript + Tailwind + Prisma",
        language="TypeScript", framework="Next.js",
        files=[TemplateFile("README.md", "# {{name}}\n\nNext.js full-stack app.\n")],
        post_install_commands=["npx -y create-next-app@latest . --typescript --tailwind --eslint"],
        tags=["fullstack", "nextjs", "typescript"],
    ),
    ProjectTemplate(
        id="node-api", name="Node.js API",
        description="Express + TypeScript + Prisma + Jest",
        language="TypeScript", framework="Express",
        files=[
            TemplateFile("src/index.ts", 'import express from "express";\nconst app = express();\napp.get("/", (_, res) => res.json({ message: "Hello from {{name}}" }));\napp.listen(3000, () => console.log("Running on :3000"));\n'),
            TemplateFile("package.json", '{"name": "{{name}}", "scripts": {"dev": "tsx watch src/index.ts"}, "dependencies": {"express": "^4.18"}, "devDependencies": {"tsx": "^4.0", "@types/express": "^4.17"}}\n'),
        ],
        tags=["api", "node", "typescript"],
    ),
    ProjectTemplate(
        id="python-ml", name="Python ML Project",
        description="PyTorch + Jupyter + MLflow",
        language="Python", framework="PyTorch",
        files=[
            TemplateFile("train.py", "import torch\nimport torch.nn as nn\nprint(f'PyTorch {torch.__version__}')\n"),
            TemplateFile("requirements.txt", "torch>=2.0\njupyterlab>=4.0\nmlflow>=2.0\nnumpy>=1.24\npandas>=2.0\nscikit-learn>=1.3\n"),
            TemplateFile("notebooks/.gitkeep", ""),
            TemplateFile("data/.gitkeep", ""),
        ],
        tags=["ml", "pytorch", "python"],
    ),
    ProjectTemplate(
        id="fullstack", name="Full-Stack (FastAPI + React)",
        description="FastAPI backend + React frontend",
        language="Python/TypeScript", framework="FastAPI+React",
        files=[
            TemplateFile("backend/main.py", 'from fastapi import FastAPI\napp = FastAPI()\n\n@app.get("/api/health")\ndef health():\n    return {"status": "ok"}\n'),
            TemplateFile("frontend/README.md", "# Frontend\n\nReact app.\n"),
            TemplateFile("README.md", "# {{name}}\n\nFull-stack application.\n"),
        ],
        tags=["fullstack", "python", "react"],
    ),
    ProjectTemplate(
        id="chrome-extension", name="Chrome Extension",
        description="Manifest V3 + TypeScript",
        language="TypeScript", framework=None,
        files=[
            TemplateFile("manifest.json", '{"manifest_version": 3, "name": "{{name}}", "version": "1.0", "action": {"default_popup": "popup.html"}}\n'),
            TemplateFile("popup.html", '<!DOCTYPE html><html><body><h1>{{name}}</h1></body></html>\n'),
        ],
        tags=["chrome", "extension", "typescript"],
    ),
    ProjectTemplate(
        id="discord-bot", name="Discord Bot",
        description="discord.py + SQLite",
        language="Python", framework="discord.py",
        files=[
            TemplateFile("bot.py", 'import discord\nfrom discord.ext import commands\n\nbot = commands.Bot(command_prefix="!", intents=discord.Intents.default())\n\n@bot.event\nasync def on_ready():\n    print(f"Bot ready: {bot.user}")\n\nbot.run("TOKEN")\n'),
            TemplateFile("requirements.txt", "discord.py>=2.3\naiosqlite>=0.19\n"),
        ],
        tags=["bot", "discord", "python"],
    ),
    ProjectTemplate(
        id="telegram-bot", name="Telegram Bot",
        description="python-telegram-bot",
        language="Python", framework="python-telegram-bot",
        files=[
            TemplateFile("bot.py", 'from telegram.ext import Application, CommandHandler\n\nasync def start(update, context):\n    await update.message.reply_text("Hello!")\n\napp = Application.builder().token("TOKEN").build()\napp.add_handler(CommandHandler("start", start))\napp.run_polling()\n'),
            TemplateFile("requirements.txt", "python-telegram-bot>=20.0\n"),
        ],
        tags=["bot", "telegram", "python"],
    ),
]


class TemplateManager:
    """Project template system with AI custom scaffolding."""

    def __init__(self, ai_provider: Any = None, console: Console | None = None) -> None:
        self.ai = ai_provider
        self.console = console or Console()

    def list_templates(self) -> list[ProjectTemplate]:
        return list(BUILT_IN_TEMPLATES)

    async def create_from_template(
        self,
        template_id: str,
        project_name: str,
        output_dir: str,
        variables: dict[str, str] | None = None,
    ) -> str:
        """Create project from template."""
        template = next((t for t in BUILT_IN_TEMPLATES if t.id == template_id), None)
        if not template:
            self.console.print(f"  [red]Template '{template_id}' not found[/]")
            return ""

        out = os.path.abspath(output_dir)
        Path(out).mkdir(parents=True, exist_ok=True)

        vars_ = {"name": project_name, **(variables or {})}

        for tf in template.files:
            content = tf.content
            for k, v in vars_.items():
                content = content.replace("{{" + k + "}}", v)
            fpath = os.path.join(out, tf.path)
            Path(fpath).parent.mkdir(parents=True, exist_ok=True)
            Path(fpath).write_text(content, encoding="utf-8")

        self.console.print(Panel(
            f"  ✅ Created '{project_name}' from [{template.name}]\n"
            f"  📁 {out}\n  📄 {len(template.files)} files",
            title=" 🚀 Project Created ", border_style="green", padding=(0, 1),
        ))

        return out

    async def create_custom(self, description: str, output_dir: str) -> str:
        """AI-powered custom project scaffolding."""
        if not self.ai:
            self.console.print("  [red]AI provider needed for custom templates[/]")
            return ""

        try:
            resp = await self.ai.chat(
                messages=[{"role": "user", "content": (
                    f"Create a project structure for: {description}\n\n"
                    "Return each file as:\nFILE: path/to/file\nCONTENT:\n```\ncode here\n```\n"
                )}],
                system="You generate project scaffolds. Return only FILE/CONTENT pairs.",
            )
            text = getattr(resp, "content", "")
            out = os.path.abspath(output_dir)
            Path(out).mkdir(parents=True, exist_ok=True)

            import re
            for match in re.finditer(r"FILE:\s*(.+?)\nCONTENT:\n```[\w]*\n(.+?)```", text, re.DOTALL):
                fpath = os.path.join(out, match.group(1).strip())
                Path(fpath).parent.mkdir(parents=True, exist_ok=True)
                Path(fpath).write_text(match.group(2), encoding="utf-8")

            self.console.print(f"  [green]✅ Custom project created at {out}[/]")
            return out
        except Exception as e:
            self.console.print(f"  [red]Error: {e}[/]")
            return ""

    async def save_as_template(self, name: str, description: str) -> ProjectTemplate:
        """Save current project as template."""
        files: list[TemplateFile] = []
        skip = {".git", "node_modules", "__pycache__", ".venv"}

        for root, dirs, fnames in os.walk(os.getcwd()):
            dirs[:] = [d for d in dirs if d not in skip]
            for fname in fnames:
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, os.getcwd())
                try:
                    content = Path(fpath).read_text(encoding="utf-8")
                    files.append(TemplateFile(path=rel, content=content[:5000]))
                except (OSError, UnicodeDecodeError):
                    continue
                if len(files) >= 50:
                    break

        template = ProjectTemplate(
            id=name.lower().replace(" ", "-"), name=name,
            description=description, files=files,
        )

        self.console.print(f"  [green]✅ Saved template '{name}' ({len(files)} files)[/]")
        return template

    def show_templates(self) -> None:
        """Display available templates."""
        table = Table(title=" 📦 Project Templates ", border_style="green")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Description")
        table.add_column("Language")

        for t in BUILT_IN_TEMPLATES:
            table.add_row(t.id, t.name, t.description, t.language)

        self.console.print(table)
