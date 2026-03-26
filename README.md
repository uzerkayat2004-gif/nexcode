# NexCode

**AI-powered coding assistant — Claude Code for everyone, with every model.**

NexCode is an open, multi-provider agentic coding CLI and web app. It's model-agnostic — plug in your own API key from any supported provider and use any model you want.

## Features

- 🤖 **Multi-Provider**: OpenAI, Anthropic, Google, Mistral, Groq, Ollama, and more
- 🔐 **Secure Auth**: OAuth with Google, GitHub, magic email, or API key
- 💻 **CLI + Web**: Use in terminal (React Ink) or browser (Monaco Editor)
- 🔒 **Encrypted**: API keys encrypted with AES-256-GCM

## Tech Stack

### CLI (`apps/cli`)
- Runtime: Bun
- Framework: Commander.js + React Ink
- Auth: Device flow + API key

### Web (`apps/web`)
- Framework: Next.js 15 (App Router) + TypeScript
- Auth: NextAuth.js v5
- API: tRPC v11
- UI: Tailwind CSS v4 + shadcn/ui
- Database: PostgreSQL via Neon + Drizzle ORM

### Shared Packages
- `@nexcode/shared` — Types, schemas, utilities
- `@nexcode/db` — Drizzle schema + migrations
- `@nexcode/ui` — Shared UI primitives

## Getting Started

### Prerequisites
- [Bun](https://bun.sh) 1.0+
- PostgreSQL database (or [Neon](https://neon.tech) account)

### Installation

```bash
# Clone the repo
git clone https://github.com/uzerkayat2004-gif/nexcode.git
cd nexcode

# Install dependencies
bun install

# Copy environment variables
cp .env.example .env
# Edit .env with your credentials

# Build all packages
bun run build
```

### Development

```bash
# Start all apps in dev mode
bun run dev

# Or start individually
bun run dev --filter=@nexcode/web
bun run dev --filter=@nexcode/cli
```

### CLI Usage

```bash
# Authenticate
nexcode auth login

# Or with API key
nexcode auth login --api-key nxc_sk_xxxxxxxx

# Check auth status
nexcode auth status

# Start chat
nexcode chat

# Configure
nexcode config set defaultProvider openai
nexcode config set defaultModel gpt-4o
```

## Project Structure

```
nexcode/
├── apps/
│   ├── cli/           # Terminal CLI (React Ink + Bun)
│   └── web/           # Next.js web dashboard
├── packages/
│   ├── shared/        # Types, schemas, utilities
│   ├── db/            # Drizzle schema + migrations
│   └── ui/            # Shared UI primitives
├── turbo.json         # Turborepo config
└── package.json       # Root workspace
```

## Authentication

NexCode supports multiple auth methods:

1. **Google OAuth** — Sign in with Google
2. **GitHub OAuth** — Sign in with GitHub
3. **Magic Email** — Passwordless sign in via email
4. **API Key** — For headless/CI usage

All credentials are encrypted with AES-256-GCM and stored in `~/.nexcode/auth.json`.

## License

MIT
