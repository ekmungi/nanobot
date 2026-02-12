# Nanobot Personal Assistant - Implementation Plan (v2)

## Key Change from v1: MCP-First Approach

The biggest shift: instead of building custom Notion/Obsidian tool plugins, we integrate **MCP client support** into nanobot. This gives us instant access to Notion, Obsidian, GitHub, filesystem, and 5,800+ other MCP servers -- with zero custom tool code per integration. The agent gets all those tools by just adding config entries.

---

## Phase Summary

| Phase | What | Code Changes | Priority |
|-------|------|-------------|----------|
| **1. Setup** | Get nanobot running with a cloud LLM | None | Do first |
| **2. Web Channel** | Browser-based chat for any device | 3 new files, 3 modified | Do second |
| **3. MCP Client** | Connect to Notion, Obsidian, and any MCP server | 2 new files, 3 modified | Do third (V1 core) |
| **4. Remote Access** | Cloudflare Tunnel + Telegram for Android | None (infrastructure) | Do fourth |
| **5. Memory Upgrade** | Compaction + BM25 search over memory | 2 modified files | After V1 |
| **6. Self-Building Agent** | Meta-tool + skill-creator for agent self-extension | 1 new skill, 1 new tool | After V1 |
| **7. Voice** | STT + TTS via web channel | 1 new file, 2 modified | After V1 |
| **8. Android PWA** | Add-to-homescreen, offline shell | 2 new files, 1 modified | After V1 |

**V1 = Phases 1-4**: A working personal assistant accessible from any device, connected to Notion and other services via MCP.

---

## Phase 1: Get Nanobot Running Locally

**Goal**: Fresh fork to working CLI assistant. No code changes.

### Steps

1. **Install Python 3.11+** (verify: `python --version`)

2. **Install nanobot in editable mode**:
   ```
   cd C:\Users\ekmun\Dev\nanobot
   pip install -e ".[dev]"
   ```

3. **Run onboard**:
   ```
   nanobot onboard
   ```
   Creates `~/.nanobot/config.json` and `~/.nanobot/workspace/` with templates.

4. **Add an API key** to `~/.nanobot/config.json`:
   ```json
   {
     "providers": {
       "anthropic": { "apiKey": "sk-ant-..." }
     },
     "agents": {
       "defaults": { "model": "anthropic/claude-sonnet-4-5" }
     }
   }
   ```

5. **Test**:
   ```
   nanobot agent -m "Hello, what can you do?"
   nanobot status
   ```

### Verification
- `nanobot agent -m "What is 2+2?"` returns a coherent answer
- `nanobot status` shows green checkmarks

---

## Phase 2: Web Chat Channel

**Goal**: Browser-based chat so any device with a browser can talk to nanobot.

### New Files

| File | Purpose |
|------|---------|
| `nanobot/channels/web.py` | WebChannel class (aiohttp + WebSocket) |
| `nanobot/channels/web_static/index.html` | Single-file web UI (~250 lines) |

### Modified Files

| File | Change |
|------|--------|
| `nanobot/config/schema.py` | Add `WebConfig` to `ChannelsConfig` |
| `nanobot/channels/manager.py` | Register web channel in `_init_channels()` |
| `pyproject.toml` | Add `aiohttp>=3.9.0` |

### Key Details
- `WebChannel` extends `BaseChannel` (same pattern as Telegram)
- aiohttp serves static HTML at `/` and WebSocket at `/ws`
- Auth: token passed as `?token=xxx` query param
- WebSocket protocol: `{"type": "message", "content": "..."}`
- Mobile-responsive, no build tools, no framework

### Config
```json
"channels": {
  "web": { "enabled": true, "port": 18800, "token": "my-secret-token" }
}
```

### Verification
1. `nanobot gateway`
2. Open `http://localhost:18800?token=my-secret-token`
3. Send message, verify response

---

## Phase 3: MCP Client Integration

**Goal**: Connect nanobot to MCP servers so it can use Notion, Obsidian, filesystem, and any other MCP-compatible service.

This is the highest-value phase because it replaces the need to build individual tool plugins for every service.

### New Files

| File | Purpose |
|------|---------|
| `nanobot/mcp/client.py` | MCP client session manager -- connects to configured MCP servers, discovers tools, routes tool calls |
| `nanobot/mcp/bridge.py` | Bridge that converts MCP tools into nanobot Tool instances so the agent loop can use them seamlessly |

### Modified Files

| File | Change |
|------|--------|
| `nanobot/config/schema.py` | Add `MCPServerConfig` model and `mcp_servers` list to `Config` |
| `nanobot/agent/loop.py` | Initialize MCP client in `__init__`, register MCP tools alongside built-in tools |
| `pyproject.toml` | Add `mcp>=1.0.0` dependency |

### How It Works

**Config** (`~/.nanobot/config.json`):
```json
{
  "mcp_servers": [
    {
      "name": "notion",
      "command": "npx",
      "args": ["-y", "@notionhq/notion-mcp-server"],
      "env": { "OPENAPI_MCP_HEADERS": "{\"Authorization\": \"Bearer ntn_...\"}" },
      "enabled": true
    },
    {
      "name": "obsidian",
      "command": "npx",
      "args": ["-y", "obsidian-mcp-server"],
      "env": { "OBSIDIAN_VAULT_PATH": "C:/Users/ekmun/Documents/MyVault" },
      "enabled": true
    },
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/ekmun/Documents"],
      "enabled": true
    }
  ]
}
```

**Startup flow**:
1. `AgentLoop.__init__` creates an `MCPClientManager`
2. `MCPClientManager` reads `config.mcp_servers`
3. For each enabled server: spawns the process, connects via stdio transport
4. Calls `session.list_tools()` on each server
5. Wraps each MCP tool as a nanobot `Tool` instance (via `MCPBridgeTool`)
6. Registers all bridge tools with the `ToolRegistry`

**MCPBridgeTool** class:
```python
class MCPBridgeTool(Tool):
    """Wraps an MCP server tool as a nanobot Tool."""

    def __init__(self, server_name, mcp_tool, session):
        self._server_name = server_name
        self._mcp_tool = mcp_tool       # From list_tools()
        self._session = session           # MCP ClientSession

    @property
    def name(self):
        return f"{self._server_name}__{self._mcp_tool.name}"

    @property
    def description(self):
        return self._mcp_tool.description

    @property
    def parameters(self):
        return self._mcp_tool.inputSchema

    async def execute(self, **kwargs):
        result = await self._session.call_tool(self._mcp_tool.name, arguments=kwargs)
        # Convert MCP result to string
        return "\n".join(c.text for c in result.content if hasattr(c, 'text'))
```

This means when the AI decides to call `notion__search`, the agent loop executes it like any other tool, but under the hood it routes to the Notion MCP server.

### Dependencies
- `mcp>=1.0.0` (official Python SDK)
- Node.js 18+ on the system (for npx-based MCP servers)

### Verification
1. Install Node.js if not present
2. Add Notion MCP server to config with API key
3. `nanobot agent -m "Search my Notion for recent notes"`
4. Verify it finds and returns Notion content

### What This Gives You Immediately
- **Notion**: Search, read, create, update pages and databases
- **Obsidian**: Read, write, search notes in your vault (when you create one)
- **Filesystem**: Secure file access in configured directories
- **And 5,800+ more**: Just add the server to config

---

## Phase 4: Remote Access + Android

**Goal**: Access nanobot from work laptop and Android phone.

### No Code Changes -- Infrastructure Only

**For work laptop** (enterprise-restricted):
1. Install `cloudflared` on home PC
2. `cloudflared tunnel --url http://localhost:18800` for quick testing
3. Set up permanent tunnel with a domain for production use
4. Access from work laptop: just open `https://nanobot.yourdomain.com?token=xxx`

**For Android phone**:
1. **Telegram** (recommended): Create a bot via @BotFather, add token to config:
   ```json
   "channels": {
     "telegram": {
       "enabled": true,
       "token": "123456:ABC-DEF...",
       "allowFrom": ["your_telegram_user_id"]
     }
   }
   ```
2. **Web PWA**: Open the tunnel URL in Chrome, tap menu > "Add to Home Screen"

### Verification
- Work laptop browser reaches nanobot through tunnel
- Android Telegram can chat with nanobot
- Android browser PWA works

---

## V1 Complete

At this point you have:
- A personal AI assistant running on your ThinkPad
- Accessible from any device (work laptop, Android, home PC)
- Connected to Notion (and any other MCP service)
- Using a cloud LLM (Claude, GPT, etc.)
- With conversation memory and session persistence

---

## Phase 5: Memory Upgrade (Post-V1)

**Goal**: Prevent forgetting in long conversations, enable search over accumulated knowledge.

### Modified Files

| File | Change |
|------|--------|
| `nanobot/agent/memory.py` | Add BM25 search index (SQLite FTS5), load yesterday's notes too, add `search_memory()` method |
| `nanobot/agent/loop.py` | Add compaction logic: before context gets too long, summarize and flush important facts to MEMORY.md |

### Key Changes

1. **BM25 search**: Instead of loading all of MEMORY.md into every prompt, index all memory files in SQLite FTS5 and retrieve only relevant chunks. Zero new dependencies (SQLite is built into Python).

2. **Compaction**: When session history exceeds a threshold (e.g., 30 messages), summarize older messages and write key facts to MEMORY.md before they leave the context window.

3. **Yesterday's notes**: Trivial change -- load `YYYY-MM-DD` for both today and yesterday to maintain continuity across midnight.

---

## Phase 6: Self-Building Agent (Post-V1)

**Goal**: The agent can create new tools and skills for itself with user approval.

### New Files

| File | Purpose |
|------|---------|
| `workspace/skills/tool-creator/SKILL.md` | Skill that teaches the agent how to find MCP servers, create tool plugins, and manage its own capabilities |
| `nanobot/agent/tools/manage_plugins.py` | Meta-tool that can search the MCP registry, add/remove MCP servers from config, create plugin scaffolds |

### How It Works
- Agent has a `manage_plugins` tool
- When it encounters a task it can't handle, it:
  1. Searches MCP registry for a matching server
  2. Suggests adding it (asks user for permission)
  3. If no MCP server exists, generates a custom tool plugin
  4. Always asks before enabling anything

---

## Phase 7: Voice (Post-V1)

**Goal**: Voice input/output via web channel.

### New Files

| File | Purpose |
|------|---------|
| `nanobot/providers/tts.py` | TTS via OpenAI `/v1/audio/speech` API |

### Modified Files

| File | Change |
|------|--------|
| `nanobot/channels/web.py` | Handle audio WebSocket messages, transcribe via Groq Whisper, respond with TTS |
| `nanobot/channels/web_static/index.html` | Add mic button (MediaRecorder API), audio playback |

---

## Phase 8: Android PWA (Post-V1)

**Goal**: App-like experience on Android.

### New Files

| File | Purpose |
|------|---------|
| `nanobot/channels/web_static/manifest.json` | PWA manifest |
| `nanobot/channels/web_static/sw.js` | Service worker for offline shell |

### Modified Files

| File | Change |
|------|--------|
| `nanobot/channels/web_static/index.html` | Manifest link, service worker registration, mobile keyboard handling |

---

## Complete File Change Map

### New files (9 total):

| File | Phase | Lines (est.) |
|------|-------|-------------|
| `nanobot/channels/web.py` | 2 | ~200 |
| `nanobot/channels/web_static/index.html` | 2 | ~250 |
| `nanobot/mcp/client.py` | 3 | ~200 |
| `nanobot/mcp/bridge.py` | 3 | ~100 |
| `workspace/skills/tool-creator/SKILL.md` | 6 | ~150 |
| `nanobot/agent/tools/manage_plugins.py` | 6 | ~150 |
| `nanobot/providers/tts.py` | 7 | ~50 |
| `nanobot/channels/web_static/manifest.json` | 8 | ~20 |
| `nanobot/channels/web_static/sw.js` | 8 | ~15 |

### Modified files (5 total):

| File | Phases | Nature of changes |
|------|--------|-------------------|
| `nanobot/config/schema.py` | 2, 3 | Add WebConfig, MCPServerConfig |
| `nanobot/channels/manager.py` | 2 | Register web channel |
| `nanobot/agent/loop.py` | 3, 5 | MCP client init, compaction logic |
| `nanobot/agent/memory.py` | 5 | BM25 search, yesterday's notes |
| `pyproject.toml` | 2, 3 | Add aiohttp, mcp dependencies |

### New dependencies (2 total):

| Package | Phase | Purpose |
|---------|-------|---------|
| `aiohttp>=3.9.0` | 2 | Web server for chat channel |
| `mcp>=1.0.0` | 3 | MCP client SDK |

---

## What's Next: Immediate Action Items

1. **Phase 1**: Install and run nanobot (takes a few commands)
2. **Phase 2**: Build the web channel (I will write the code)
3. **Phase 3**: Integrate MCP client (I will write the code)
4. **Phase 4**: Set up Cloudflare Tunnel + Telegram (configuration)

Ready to start with Phase 1?
