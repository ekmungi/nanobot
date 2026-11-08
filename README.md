<div align="center">
  <img src="nanobot_logo.png" alt="nanobot" width="500">
  <h1>nanobot: Personal AI Assistant</h1>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

A personal AI assistant built on the [nanobot](https://github.com/HKUDS/nanobot) framework. Features Notion integration with meeting transcript extraction, a Claude Desktop-inspired web UI, and a native Windows desktop app.

## What This Fork Adds

- **Notion MCP Integration** — Semantic wrappers for Notion's remote MCP server with 97.6% transcript extraction completeness, response compression (99.5% for search), and dual-server fallback
- **Web UI Refactor** — Claude Desktop-inspired dark theme with sidebar chat history, markdown rendering, and responsive design
- **Desktop App** — Electron-based native Windows application
- **OpenRouter Provider** — Configured for `gpt-5-nano` via OpenRouter with 120s timeout and token usage logging
- **MCP Semantic Wrappers** — Abstraction layer that hides raw MCP tool names from the LLM, with automatic response compression for small context windows

## Architecture

<p align="center">
  <img src="nanobot_arch.png" alt="nanobot architecture" width="800">
</p>

```
User Message → Channel (web/cli/telegram)
    → MessageBus → AgentLoop
        → ContextBuilder (system prompt + skills + history)
        → LLMProvider.chat() (via LiteLLM)
        → ToolRegistry.execute() (built-in tools + MCP wrappers)
        → Response → Channel
```

## Quick Start

**Prerequisites:** Python 3.11+, [uv](https://github.com/astral-sh/uv), Node.js 18+ (for MCP bridges)

**1. Clone and install**

```bash
git clone https://github.com/ekmungi/nanobot.git
cd nanobot
uv sync
```

**2. Initialize**

```bash
uv run python -m nanobot onboard
```

**3. Configure** (`~/.nanobot/config.json`)

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "openrouter/openai/gpt-5-nano"
    }
  }
}
```

**4. Chat**

```bash
uv run python -m nanobot agent -m "What is 2+2?"
```

**5. Start the web gateway**

```bash
uv run python -m nanobot gateway
# Open: http://localhost:18800
```

## Web Interface

Access via browser at `http://localhost:18800` after starting the gateway.

**Features:**
- Claude Desktop-inspired dark theme
- Left sidebar with chat history
- Markdown support with syntax highlighting
- Chat persistence with localStorage
- Responsive design for mobile and desktop
- Real-time WebSocket connection with status indicator

## Desktop Application

Native Windows app built with Electron, wrapping the same web UI.

**Run from source:**

```bash
cd desktop
npm install
npm start          # Run app
npm run dev        # Run with DevTools
npm run build:win  # Create Windows installer
```

**Output:** Creates installers in `desktop/dist/`.

## Notion Integration

This fork's primary enhancement. Uses Notion's remote MCP server (`mcp.notion.com`) with semantic wrappers that:

- **Search** Notion workspace with compressed results (311K → 1.6K chars)
- **Read pages** with full meeting transcript extraction (`include_transcript: true`)
- **Query databases**, **create pages**, and **update pages**
- **Auto-intercept** Notion URLs from `web_fetch` and redirect to `notion_read_page`
- **Dual-server fallback** — remote primary, local (`@notionhq/notion-mcp-server`) as backup

5 semantic wrapper tools: `notion_search`, `notion_read_page`, `notion_query_database`, `notion_create_page`, `notion_update_page`

## Configuration

Config file: `~/.nanobot/config.json`

### Providers

| Provider | Purpose | Get API Key |
|----------|---------|-------------|
| `openrouter` | LLM (recommended, access to all models) | [openrouter.ai](https://openrouter.ai) |
| `anthropic` | LLM (Claude direct) | [console.anthropic.com](https://console.anthropic.com) |
| `openai` | LLM (GPT direct) | [platform.openai.com](https://platform.openai.com) |
| `deepseek` | LLM (DeepSeek direct) | [platform.deepseek.com](https://platform.deepseek.com) |
| `groq` | LLM + Voice transcription (Whisper) | [console.groq.com](https://console.groq.com) |
| `vllm` | LLM (local, any OpenAI-compatible server) | — |

<details>
<summary><b>Adding a New Provider</b></summary>

Only 2 steps:

1. Add a `ProviderSpec` to `PROVIDERS` in `nanobot/providers/registry.py`
2. Add a `ProviderConfig` field to `ProvidersConfig` in `nanobot/config/schema.py`

Environment variables, model prefixing, and status display work automatically.

</details>

### MCP Servers

Configure in `~/.nanobot/config.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.notion.com/mcp"],
      "semanticWrappers": true
    }
  }
}
```

### Security

| Option | Default | Description |
|--------|---------|-------------|
| `tools.restrictToWorkspace` | `false` | Sandbox agent to workspace directory |
| `channels.*.allowFrom` | `[]` | Whitelist user IDs (empty = allow all) |

See [docs/SECURITY.md](docs/SECURITY.md) for full security policy.

## Chat Channels

| Channel | Setup |
|---------|-------|
| **Web** | Built-in, `http://localhost:18800` |
| **Desktop** | Electron app in `desktop/` |
| **Telegram** | Bot token in config |
| **Discord** | Bot token + intents |
| **WhatsApp** | QR code scan |

## CLI Reference

| Command | Description |
|---------|-------------|
| `nanobot onboard` | Initialize config and workspace |
| `nanobot agent -m "..."` | Chat with the agent |
| `nanobot agent` | Interactive chat mode |
| `nanobot gateway` | Start the gateway (web + all channels) |
| `nanobot status` | Show status |

## Project Structure

```
nanobot/
├── desktop/            # Electron desktop app
├── docs/               # Public documentation
│   ├── ARCHITECTURE.md
│   ├── SECURITY.md
│   ├── SETUP_GUIDE.md
│   └── QUICKSTART_UI.md
├── tests/              # Test files
├── nanobot/            # Source code
│   ├── agent/          # Core agent (loop, context, tools)
│   ├── channels/       # Web, Telegram, Discord, etc.
│   ├── cli/            # CLI commands
│   ├── config/         # Configuration (Pydantic schema + loader)
│   ├── mcp/            # MCP integration (client, bridge, wrappers)
│   ├── providers/      # LLM providers (LiteLLM-based)
│   ├── session/        # Conversation sessions
│   └── skills/         # Agent skills (Notion, cron, GitHub, etc.)
├── pyproject.toml      # Python project config
└── Dockerfile          # Container support
```

## Development

The project is managed with `uv`, and its virtual environment is `.venv/`. On Windows, start Python through `uv run python` rather than a bare `python`, so that the project's environment is used. Each test file runs on its own with `uv run python tests/test_<name>.py`. The web UI is the single file `nanobot/channels/web_static/index.html` and has no build step, so you edit it and refresh the browser while the gateway runs.

## Docker

```bash
docker build -t nanobot .
docker run -v ~/.nanobot:/root/.nanobot -p 18790:18790 -p 18800:18800 nanobot gateway
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design, components, data flow |
| [Security](docs/SECURITY.md) | Security policy, API key management |
| [Setup Guide](docs/SETUP_GUIDE.md) | Detailed installation and configuration |
| [UI Quick Start](docs/QUICKSTART_UI.md) | Getting started with web and desktop UI |

## Credits

Built on [nanobot](https://github.com/HKUDS/nanobot) by HKUDS. This fork adds Notion MCP integration, web UI redesign, and desktop app support.

<p align="center">
  <sub>For personal use, educational, and research purposes</sub>
</p>
