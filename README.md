# NexCode

> A powerful, production-grade AI coding assistant for the terminal — inspired by Claude Code, built to go further.

## Features

- 🤖 **Multi-provider AI** — Claude, GPT, Gemini, and more via LiteLLM
- 🎨 **Beautiful terminal UI** — Rich-powered colored output, panels, and spinners
- 🔧 **Extensible tool system** — File editing, shell commands, search, and custom tools
- 📝 **Session memory** — Persistent conversation history across sessions
- ⚙️ **Flexible config** — TOML-based configuration with sensible defaults
- 🔒 **Permission modes** — Ask, auto, or strict permission control for tool use

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd nexcode

# Install with uv
uv sync

# Run NexCode
uv run python main.py
```

### Configuration

Copy and customize the default config:

```bash
cp .nexcode.toml ~/.nexcode.toml
```

Set your API key:

```toml
[api_keys]
anthropic = "sk-ant-..."
```

Or via environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Project Structure

```
nexcode/
├── main.py                  # CLI entry point
├── pyproject.toml           # Project config & dependencies
├── .nexcode.toml            # Default user config
├── nexcode/
│   ├── app.py               # Main app orchestrator
│   ├── config.py            # Config loader & manager
│   ├── display.py           # Rich terminal UI
│   ├── history.py           # Conversation history
│   ├── ai/
│   │   └── provider.py      # AI provider abstraction
│   ├── tools/
│   │   └── registry.py      # Tool registry
│   ├── memory/
│   │   └── session.py       # Session manager
│   └── utils/
│       └── helpers.py       # Shared utilities
```

## License

MIT
