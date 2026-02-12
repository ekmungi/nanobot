# Nanobot Personal Assistant - Setup Guide

## What You Have Now

After the implementation work, your nanobot fork has three new capabilities:

1. **Web Chat Channel** - Browser-based chat accessible from any device
2. **MCP Client Integration** - Connect to any MCP server (Notion, Obsidian, filesystem, etc.)
3. **Windows Unicode Fix** - Proper emoji/Unicode handling on Windows terminals

---

## Prerequisites

- **Python 3.11+** (you have 3.12.11 via uv)
- **uv** package manager (already installed)
- **An LLM API key** (you have Gemini configured)

---

## Step 1: Install & Configure

You've already done this, but for reference:

```powershell
# Clone your fork
cd C:\Users\ekmun\Dev\nanobot

# Create venv and install
uv venv
uv pip install -e ".[dev]"

# Initialize config and workspace
$env:PYTHONUTF8=1; .venv\Scripts\python.exe -m nanobot onboard
```

### Config Location

`~/.nanobot/config.json` (i.e., `C:\Users\ekmun\.nanobot\config.json`)

### Add Your API Key

Edit `~/.nanobot/config.json` and add your key under `providers`:

```json
"providers": {
  "gemini": {
    "apiKey": "YOUR_GEMINI_API_KEY"
  }
}
```

Set your preferred model under `agents.defaults`:

```json
"agents": {
  "defaults": {
    "model": "gemini/gemini-2.0-flash"
  }
}
```

**Supported providers**: anthropic, openai, gemini, deepseek, groq, openrouter, zhipu, dashscope, moonshot, vllm (local), aihubmix

### Verify

```powershell
.venv\Scripts\python.exe -m nanobot status
```

Expected output:
```
[nb] nanobot Status

Config: C:\Users\ekmun\.nanobot\config.json OK
Workspace: C:\Users\ekmun\.nanobot\workspace OK
Model: gemini/gemini-2.0-flash
Gemini: OK
Web channel: OK http://0.0.0.0:18800
MCP servers: none configured
```

---

## Step 2: Test the CLI Agent

```powershell
.venv\Scripts\python.exe -m nanobot agent -m "Hello, what can you do?"
```

Or interactive mode:

```powershell
.venv\Scripts\python.exe -m nanobot agent
```

> **Note**: If you get a 429 rate limit error with Gemini free tier, either wait for the quota to reset or switch to a paid API key. You can use any provider - just add the key and change the model name.

---

## Step 3: Start the Gateway (Web Chat + All Channels)

```powershell
.venv\Scripts\python.exe -m nanobot gateway
```

This starts:
- The **agent loop** (processes messages)
- The **web channel** on port 18800
- Any other enabled channels (Telegram, Discord, etc.)
- Cron scheduler and heartbeat service

### Access the Web Chat

Open in any browser:
```
http://localhost:18800?token=nanobot-dev-2024
```

From another device on the same WiFi:
```
http://YOUR_PC_IP:18800?token=nanobot-dev-2024
```

Find your PC's IP:
```powershell
ipconfig | findstr "IPv4"
```

### Web Chat Token

The token is set in `~/.nanobot/config.json` under `channels.web.token`. Change it to something secure:

```json
"channels": {
  "web": {
    "enabled": true,
    "port": 18800,
    "token": "your-secret-token-here"
  }
}
```

---

## Step 4: Add MCP Servers (Notion, Obsidian, etc.)

MCP (Model Context Protocol) lets you connect external tools to your agent. Instead of writing custom integrations, you configure MCP servers that expose tools the agent can use.

### How It Works

1. You add MCP server configs to `~/.nanobot/config.json`
2. When the gateway starts, it connects to each server via stdio
3. The server's tools appear as regular tools the agent can use
4. Tool names are prefixed: `servername__toolname` (e.g., `filesystem__read_file`)

### Example: Filesystem MCP Server

The simplest MCP server to test with. Install it first:

```powershell
npm install -g @modelcontextprotocol/server-filesystem
```

Then add to your config:

```json
{
  "mcpServers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/ekmun/Documents"],
      "env": {},
      "enabled": true
    }
  ]
}
```

### Example: Notion MCP Server

```powershell
npm install -g @notionhq/notion-mcp-server
```

1. Create an integration at https://www.notion.so/my-integrations
2. Copy the API key (starts with `ntn_`)
3. Share your pages/databases with the integration
4. Add to config:

```json
{
  "mcpServers": [
    {
      "name": "notion",
      "command": "npx",
      "args": ["-y", "@notionhq/notion-mcp-server"],
      "env": {
        "NOTION_TOKEN": "ntn_YOUR_KEY_HERE"
      },
      "enabled": true
    }
  ]
}
```

Now you can say: "Search my Notion for meeting notes" or "Create a page in Notion titled 'Ideas'"

### Example: Obsidian MCP Server

For direct filesystem access to your Obsidian vault:

```json
{
  "mcpServers": [
    {
      "name": "obsidian",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/ekmun/path/to/your/vault"],
      "env": {},
      "enabled": true
    }
  ]
}
```

Or use a dedicated Obsidian MCP server if one exists:
```powershell
npm install -g obsidian-mcp-server
```

### Finding More MCP Servers

Browse available servers at:
- https://github.com/modelcontextprotocol/servers
- https://mcpservers.org

Popular options:
- **Google Drive**: `@anthropic/mcp-server-gdrive`
- **GitHub**: `@modelcontextprotocol/server-github`
- **Brave Search**: `@anthropic/mcp-server-brave-search`
- **SQLite**: `@modelcontextprotocol/server-sqlite`

### Verify MCP Configuration

After adding servers, run:
```powershell
.venv\Scripts\python.exe -m nanobot status
```

You should see:
```
MCP servers: OK 2 configured
  - notion (npx -y @notionhq/notion-mcp-server)
  - filesystem (npx -y @modelcontextprotocol/server-filesystem)
```

---

## Step 5: Remote Access (From Work Laptop / Phone)

The web chat is accessible from any device that can reach your PC. For access outside your home network:

### Option A: Cloudflare Tunnel (Recommended - Free)

1. Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/

2. Quick test (temporary URL):
```powershell
cloudflared tunnel --url http://localhost:18800
```
This gives you a temporary `https://something.trycloudflare.com` URL.

3. For a permanent URL, create a named tunnel with a custom domain.

### Why This Works for Enterprise Laptops

It's just HTTPS to a normal-looking domain. No VPN, no apps to install, no blocked ports. Just open the URL in a browser and start chatting.

### Option B: Tailscale

If you prefer a VPN approach:
1. Install Tailscale on your home PC and work device
2. Access via Tailscale IP: `http://100.x.x.x:18800?token=your-token`

---

## Quick Reference

### Commands

| Command | What it does |
|---------|-------------|
| `nanobot status` | Show configuration status |
| `nanobot agent -m "Hello"` | Send single message |
| `nanobot agent` | Interactive chat mode |
| `nanobot gateway` | Start all services (web, channels, cron) |
| `nanobot cron list` | List scheduled jobs |
| `nanobot cron add --name "daily" --cron "0 9 * * *" -m "Good morning"` | Add scheduled task |

### File Locations

| Path | Purpose |
|------|---------|
| `~/.nanobot/config.json` | Main configuration |
| `~/.nanobot/workspace/` | Agent workspace (skills, memory, notes) |
| `~/.nanobot/workspace/AGENTS.md` | Agent behavior instructions |
| `~/.nanobot/workspace/SOUL.md` | Agent personality |
| `~/.nanobot/workspace/USER.md` | Info about you |
| `~/.nanobot/workspace/memory/MEMORY.md` | Long-term memory |

### Config Structure

```json
{
  "agents": {
    "defaults": {
      "model": "gemini/gemini-2.0-flash",
      "maxTokens": 8192,
      "temperature": 0.7,
      "maxToolIterations": 20
    }
  },
  "channels": {
    "web": {
      "enabled": true,
      "port": 18800,
      "token": "your-secret-token"
    },
    "telegram": {
      "enabled": false,
      "token": "BOT_TOKEN_FROM_BOTFATHER"
    }
  },
  "providers": {
    "gemini": { "apiKey": "..." },
    "anthropic": { "apiKey": "..." },
    "openai": { "apiKey": "..." }
  },
  "tools": {
    "web": { "search": { "apiKey": "BRAVE_API_KEY" } },
    "exec": { "timeout": 60 },
    "restrictToWorkspace": false
  },
  "mcpServers": [
    {
      "name": "notion",
      "command": "npx",
      "args": ["-y", "@notionhq/notion-mcp-server"],
      "env": { "NOTION_TOKEN": "ntn_..." },
      "enabled": true
    }
  ]
}
```

---

## What Was Built (Summary of Changes)

### New Files

| File | Purpose |
|------|---------|
| `nanobot/channels/web.py` | Web chat channel (aiohttp + WebSocket) |
| `nanobot/channels/web_static/index.html` | Browser chat UI (single-file, no build tools) |
| `nanobot/mcp/__init__.py` | MCP module |
| `nanobot/mcp/client.py` | MCP client manager (connects to MCP servers) |
| `nanobot/mcp/bridge.py` | Bridges MCP tools into nanobot's tool registry |

### Modified Files

| File | Changes |
|------|---------|
| `nanobot/config/schema.py` | Added `WebConfig`, `MCPServerConfig`, wired into `ChannelsConfig` and `Config` |
| `nanobot/channels/manager.py` | Registers web channel when enabled |
| `nanobot/agent/loop.py` | Accepts `mcp_server_configs`, starts MCP on run, `cleanup()` method |
| `nanobot/cli/commands.py` | Passes MCP configs to agent, MCP status display, Windows Unicode fix |
| `nanobot/__init__.py` | Windows-safe ASCII logo fallback |
| `pyproject.toml` | Added `aiohttp>=3.9.0` and `mcp>=1.0.0` dependencies |

---

## Troubleshooting

### "429 Resource Exhausted" / Rate Limit

Your Gemini free tier quota is exhausted. Options:
1. Wait for quota to reset (resets daily)
2. Enable billing on Google AI Studio
3. Switch to another provider (add a different API key and change the model)

### Unicode/Emoji Errors on Windows

The code already handles this, but if you see encoding errors in other tools:
```powershell
$env:PYTHONUTF8=1
$env:PYTHONIOENCODING="utf-8"
```

### MCP Server Won't Connect

1. Test the MCP server standalone first:
   ```powershell
   npx -y @modelcontextprotocol/server-filesystem C:\Users\ekmun\Documents
   ```
   (Should start without errors)

2. Check the gateway logs for MCP connection errors
3. Make sure `node` and `npx` are in your PATH

### Web Chat Won't Connect

1. Make sure gateway is running: `nanobot gateway`
2. Check the port isn't blocked: `netstat -an | findstr 18800`
3. Verify token matches config
4. For remote access, check firewall allows port 18800

---

## Next Steps (Future Phases)

These are planned but not yet implemented:

- **Voice Input/Output** - STT via Groq, TTS via OpenAI API
- **Android PWA** - Add-to-home-screen for app-like experience
- **Telegram Channel** - For Android push notifications
- **Subagent Smart Routing** - Use small local models for background tasks
- **Plugin Self-Creation** - Agent creates its own tools when needed
