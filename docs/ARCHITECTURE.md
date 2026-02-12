# Nanobot Architecture Guide

## For: Personal Assistant Development (v2 - Updated)

---

## 1. What Is Nanobot? (The Simple Version)

Think of nanobot as a **switchboard operator** sitting between you and an AI brain.

```
YOU (phone, laptop, browser)
    |
    v
CHANNEL (how you talk to it: web browser, Telegram, etc.)
    |
    v
MESSAGE BUS (a mailbox - messages go in, responses come out)
    |
    v
AGENT LOOP (the brain - reads your message, thinks, uses tools, replies)
    |
    +---> MCP CLIENT (connects to any MCP server for tools)
    +---> BUILT-IN TOOLS (file, web, shell, etc.)
    +---> SUBAGENTS (delegate to smaller models for specific tasks)
    |
    v
LLM PROVIDER (the actual AI model - Claude, GPT, Gemini, or a local model)
```

**That's the whole thing.** Everything else is just details about each box.

---

## 2. The Six Core Pieces

### Piece 1: Channels (How You Talk To It)

A **channel** is any way you send messages to nanobot. Think of it like different phone lines.

- **Web browser** - You type in a chat box in your browser (works on any device)
- **Telegram** - You message a Telegram bot (best for Android)
- **Discord** - You message a Discord bot
- **WhatsApp** - You message via WhatsApp
- **CLI** - You type directly in a terminal

Each channel does the same three things:
1. **Listen** for your messages
2. **Forward** them to the message bus
3. **Send back** the response to you

**To add a new channel**: Create a file that knows how to listen for messages from a new platform and send responses back. That's it.

### Piece 2: Message Bus (The Mailbox)

The message bus is just two queues (like two trays on a desk):

- **Inbound tray**: Messages from you waiting to be processed
- **Outbound tray**: Responses waiting to be sent back to you

This is what keeps everything separate. The channel doesn't need to know about the AI. The AI doesn't need to know about the channel. They just put messages in trays and pick them up.

### Piece 3: Agent Loop (The Brain)

The agent loop is the core. When a message arrives, it:

1. **Loads your conversation history** (so it remembers what you said before)
2. **Builds a prompt** with your message + history + personality + knowledge + skills
3. **Sends it to the AI model** (Claude, GPT, etc.)
4. **If the AI wants to use a tool** (search the web, read a file, check Notion): executes the tool, sends the result back to the AI, and repeats
5. **When the AI has a final answer**: sends it back through the outbound tray

The key insight: **the agent can use tools in a loop**. It might search the web, read the results, then search again, then write a file, then respond. This loop (up to 20 iterations) is what makes it an "agent" rather than just a chatbot.

### Piece 4: Tools (What The Agent Can Do)

Tools are **actions** the AI can take. There are two ways tools get into the system:

**A. Built-in tools** (hardcoded in nanobot):
| Tool | What it does |
|------|-------------|
| `read_file` | Read a file from disk |
| `write_file` | Create or overwrite a file |
| `edit_file` | Find and replace text in a file |
| `list_dir` | List files in a directory |
| `exec` | Run a shell command |
| `web_search` | Search the web (via Brave) |
| `web_fetch` | Fetch and read a web page |
| `message` | Send a message to a chat |
| `spawn` | Start a background task |
| `cron` | Schedule recurring tasks |

**B. MCP tools** (from external MCP servers -- see Piece 6):
These are discovered automatically. You configure which MCP servers to connect to, and their tools appear for the agent to use. Notion, GitHub, filesystem, and 5,800+ other MCP servers already exist.

**C. Self-created tools**: The agent can also create new tools on the fly (see Section 6).

### Piece 5: LLM Provider (The AI Model)

The provider is which AI actually processes your messages. Nanobot uses LiteLLM, which is a universal translator for AI APIs. This means you can use:

- **Cloud**: Anthropic (Claude), OpenAI (GPT), Google (Gemini), DeepSeek, Groq, and more
- **Local**: Any model running via Ollama, vLLM, or similar on your machine or a dedicated mini PC

You pick which one in config. You can switch at any time. You can also use **different models for different purposes** -- a large model (Claude, GPT-4) for your main conversations and a small local model (Qwen 2.5 7B, Llama 3.2 3B) for subagent tasks that don't need heavy reasoning.

### Piece 6: MCP Client (The Universal Tool Connector)

**MCP (Model Context Protocol)** is the industry standard for connecting AI agents to external tools and data. Think of it like USB for AI -- one connector that works with everything.

Instead of writing custom code for every service (Notion, GitHub, Google Calendar, etc.), nanobot connects to **MCP servers** that already exist:

```
nanobot (MCP client)
    |
    ├──> Notion MCP server (search, create, update pages)
    ├──> GitHub MCP server (repos, issues, PRs)
    ├──> Filesystem MCP server (read/write files)
    ├──> Brave Search MCP server (web search)
    ├──> Memory MCP server (persistent knowledge graph)
    └──> ... 5,800+ more servers available
```

**Why this matters**: You don't have to build a Notion integration. Someone already built the official Notion MCP server (maintained by Notion themselves). You just point nanobot at it and all Notion tools appear automatically.

**How it works**:
1. You list MCP servers in config (name + command to start them)
2. At startup, nanobot connects to each server
3. Nanobot asks each server "what tools do you have?"
4. Those tools get added to the agent's available tools -- automatically
5. When the AI calls one of those tools, nanobot routes it to the right server

---

## 3. How A Message Flows (Step By Step)

Here's exactly what happens when you type "What's the weather in NYC?" in the web browser:

```
1. You type in browser
2. Browser sends WebSocket message to WebChannel
3. WebChannel creates an InboundMessage:
   - channel: "web"
   - sender_id: "web_user"
   - chat_id: "abc123"
   - content: "What's the weather in NYC?"
4. WebChannel puts it in the inbound tray (message bus)

5. AgentLoop picks up the message from the inbound tray
6. Loads conversation history for "web:abc123"
7. Builds system prompt (personality + memory + skills summary)
8. Sends to Claude/GPT: "User asks: What's the weather in NYC?"

9. AI responds: "I'll search for the weather" + tool call: web_search("weather NYC")
10. AgentLoop executes web_search tool
11. Gets results: "NYC: 45F, partly cloudy..."
12. Sends results back to AI

13. AI responds: "The weather in NYC is 45F and partly cloudy."
14. AgentLoop creates OutboundMessage:
    - channel: "web"
    - chat_id: "abc123"
    - content: "The weather in NYC is 45F and partly cloudy."
15. Puts it in the outbound tray

16. ChannelManager picks up from outbound tray
17. Routes to WebChannel (because channel = "web")
18. WebChannel sends via WebSocket to your browser
19. You see the response
```

---

## 4. The Plugin Architecture (How To Extend It)

### The Core Idea

Everything in nanobot beyond the core agent loop is a **plugin** that can be turned on and off. Plugins are organized by what they do:

```
PLUGIN TYPES:
├── Tool Plugins (give the agent new abilities)
│   ├── Built-in: file, web, shell, cron, spawn
│   ├── MCP: notion, github, filesystem, memory (via MCP servers)
│   └── Custom: anything you build or the agent builds for itself
│
├── Channel Plugins (new ways to talk to the agent)
│   ├── web (browser chat)
│   ├── telegram (Telegram bot -- best for Android)
│   └── ... any messaging platform
│
├── Skill Plugins (knowledge and procedures the agent can use)
│   ├── weather, github, summarize (built-in)
│   └── your custom skills (in workspace/skills/)
│
└── MCP Servers (external tool providers)
    ├── notion, github, filesystem (community-maintained)
    └── custom MCP servers you build or find
```

### How Plugin Config Works

```json
{
  "plugins": {
    "notion": {
      "enabled": true,
      "apiKey": "ntn_..."
    },
    "web_channel": {
      "enabled": true,
      "port": 18800,
      "token": "my-secret"
    },
    "voice": {
      "enabled": true,
      "sttProvider": "groq",
      "ttsProvider": "openai"
    }
  },
  "mcp_servers": [
    {
      "name": "notion",
      "command": "npx",
      "args": ["-y", "@notionhq/notion-mcp-server"],
      "env": { "NOTION_API_KEY": "ntn_..." }
    },
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "~/Documents"]
    }
  ]
}
```

Toggle `"enabled": true/false` to turn any plugin on or off. No code changes needed.

**Future: Admin UI**. A simple web-based settings page (accessible from the same web channel) where you can toggle plugins, configure API keys, and manage MCP servers visually. This is not in V1, but the architecture supports it because all plugin state is in the config JSON.

### How Plugin Discovery Works

Plugins live in a `plugins/` directory (either built-in or in your workspace):

```
~/.nanobot/
├── config.json
├── workspace/
│   ├── skills/              <-- Skill plugins (markdown knowledge)
│   └── plugins/             <-- Custom tool/channel plugins
│       ├── my_tool/
│       │   ├── plugin.json
│       │   └── tools.py
│       └── my_channel/
│           ├── plugin.json
│           └── channel.py
│
nanobot/
└── plugins/                 <-- Built-in plugins
    ├── web_channel/
    └── voice/
```

At startup, nanobot scans both directories, reads `plugin.json` for each, checks if it's enabled in config, and loads it. This follows the exact same pattern the **skills system** already uses.

---

## 5. Multi-Agent Architecture (Talking To Other Agents)

### What It Means

Your personal agent can **delegate work** to other agents. Think of it like having a team:

```
YOU
 |
 v
YOUR PERSONAL AGENT (nanobot - uses a large model like Claude)
 |
 ├──> Research Subagent (uses a small local model for simple lookups)
 ├──> Notion (via MCP - not an agent, just tools)
 ├──> NotebookLM (via MCP or API connector)
 └──> File Organization Subagent (uses a small model for batch work)
```

### Smart Model Selection

The main agent should use the best model available (Claude, GPT-4) for your conversations -- it needs strong reasoning, nuance, and context management.

But **subagents don't always need the biggest model**. When the main agent spawns a background task like "search the web for X and summarize," a smaller, cheaper, faster model works fine. The architecture supports this:

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-sonnet-4-5"
    },
    "subagent": {
      "model": "ollama/qwen2.5:7b"
    }
  }
}
```

This way, your main conversations are high quality, but routine background tasks use a local model that's free and fast.

### How External Agents Work (MCP)

MCP is not just for tools -- it's also the standard protocol for agents to talk to each other. When you connect to an MCP server, you get:

- **Tools**: Actions the server can perform (e.g., Notion: create page, search)
- **Resources**: Data the server can provide (e.g., file contents, database records)
- **Prompts**: Pre-built prompt templates the server offers

This means connecting to a NotebookLM MCP server (when available) would instantly give your agent the ability to create notebooks, generate summaries, and create audio overviews -- without writing any code.

### MCP Server Examples Already Available

| MCP Server | What it provides | Status |
|-----------|------------------|--------|
| Notion (official) | Search, query databases, create/update pages | Available now |
| GitHub | Repos, issues, PRs, code search | Available now |
| Filesystem | Secure file read/write/search | Available now |
| Brave Search | Web and local search | Available now |
| Memory | Knowledge graph-based persistent memory | Available now |
| Docker | Container management | Available now |
| Obsidian | Vault integration, search, file management | Available now |
| Sequential Thinking | Dynamic problem-solving | Available now |
| Todoist | Task management | Available now |
| Slack, Gmail | Messaging, email | Available now |

There are 5,800+ MCP servers available today. MCP is maintained by the Linux Foundation and adopted by Anthropic, OpenAI, Google, and Microsoft.

---

## 6. Self-Building Agent (Creating Its Own Tools)

### The Concept

One of the most powerful features we'll build: the agent can **create new tools for itself** when it encounters a task it can't currently handle.

**How it works in conversation**:

```
You: "Can you check my Google Calendar for today's meetings?"

Agent: "I don't currently have a Google Calendar tool. Would you like me to
        create one? I'll need:
        1. A Google Calendar API key (I can guide you through getting one)
        2. Your permission to create the tool

        Alternatively, there's a Google Calendar MCP server available.
        I can add it to the config instead -- that would be simpler."

You: "Use the MCP server approach."

Agent: "Done. I've added the Google Calendar MCP server to your config.
        Let me restart the connection... Now checking your calendar.
        You have 3 meetings today: ..."
```

### How It's Implemented

The agent gets a **meta-tool** called `create_tool` (or `manage_plugins`) that can:

1. **Search the MCP registry** for existing servers that match the need
2. **Suggest adding an MCP server** to the config (simplest approach)
3. **Generate a custom tool plugin** if no MCP server exists (writes the Python code, following the Tool base class template)
4. **Ask the user** before making changes (always -- never silently)

The agent already has `write_file` and `exec` tools, so it can technically create Python files already. The `create_tool` meta-tool wraps this in a structured workflow with:
- A template for the `plugin.json` and `tools.py` files
- Validation that the generated code follows the Tool interface
- User confirmation before enabling
- Guidance built into a **Skill** (see next section)

### Safety

- The agent always asks for permission before creating or enabling new tools
- Generated tools are placed in `~/.nanobot/workspace/plugins/` (user space, not system)
- Each new tool starts disabled until the user confirms
- The agent explains what the tool does in plain language before enabling

---

## 7. Skills System (Procedural Knowledge)

### What Skills Are

Skills are **instructions that teach the agent how to do things**. Think of them as training manuals.

Anthropic has formalized this as an open standard called **Agent Skills**. The concept: instead of stuffing everything into the system prompt (which wastes context and makes the AI slower), Skills are loaded **on demand** when relevant.

### How Skills Work (Three Levels)

```
Level 1: METADATA (always loaded, ~100 tokens each)
  "I know a skill called 'github' that helps with GitHub operations"

Level 2: INSTRUCTIONS (loaded when relevant, <5k tokens)
  The full skill content: how to create PRs, manage issues, etc.

Level 3: RESOURCES (loaded only when executing, unlimited)
  Scripts, templates, reference docs that the skill bundles
```

This means you can have 50 skills installed but only pay the context cost of the 2-3 relevant to the current conversation.

### Nanobot Already Has This

The skills system in nanobot already follows this pattern:
- Skills live in `workspace/skills/<name>/SKILL.md` (markdown files)
- Metadata is scanned at startup (Level 1)
- Full content loaded on demand via `read_file` (Level 2)
- Supporting files in the skill directory (Level 3)

### Built-in Skills

| Skill | What it teaches the agent |
|-------|--------------------------|
| `github` | How to work with GitHub repos, PRs, issues |
| `weather` | How to check weather forecasts |
| `summarize` | How to create good summaries |
| `cron` | How to manage scheduled tasks |
| `skill-creator` | How to create new skills (meta-skill) |

### The Skill-Creator Skill

This is the meta-skill that teaches the agent how to build new skills and tools. It contains:
- The template for `SKILL.md` files
- The template for `plugin.json` and `tools.py` files
- Instructions on when to create a skill vs. a tool vs. suggest an MCP server
- Guidelines for asking the user for preferences and confirmation

This is what enables the self-building behavior described in Section 6.

---

## 8. Memory & Knowledge System

### How The Agent Remembers Things

The memory system is designed around a principle from OpenClaw/Clawdbot: **treat the AI's context window as a cache, and markdown files as the source of truth**.

```
MEMORY LAYERS:
├── Session History (short-term cache)
│   └── Recent messages in the current conversation
│       Stored in ~/.nanobot/sessions/ as JSONL files
│       Compacted (summarized) when it gets too long
│
├── Daily Notes (medium-term)
│   └── Today's + yesterday's activity notes
│       Stored in workspace/memory/YYYY-MM-DD.md
│       Agent writes important things here before they fade from context
│
├── Long-term Memory (permanent facts)
│   └── Key facts, preferences, decisions
│       Stored in workspace/memory/MEMORY.md
│       Human-readable, git-friendly, editable by you
│
├── Search Index (retrieval layer)
│   └── BM25 keyword search over all memory files
│       Stored in SQLite (lightweight, no external service)
│       Finds relevant memories without loading everything
│
└── Skills (procedural knowledge)
    └── How-to guides loaded on demand
        Stored as markdown in workspace/skills/
```

### Key Design Decisions

**Markdown as source of truth**: All memory is stored in plain markdown files. You can read them, edit them, version them with git, and sync them across devices. No proprietary database format.

**Search before load**: Instead of loading all of MEMORY.md into every conversation (wasteful for large memory files), the agent searches for relevant chunks first and only loads what's needed. Initially this uses BM25 keyword search (built into SQLite, zero dependencies). Later, vector embeddings can be added for semantic search.

**Compaction**: When a conversation gets long, the agent summarizes older messages and writes important facts to MEMORY.md before they leave the context window. This prevents "forgetting" during long sessions.

**Memory fits on disk, not in RAM**: Since the ThinkPad X1 has limited resources, the memory system is designed to be lightweight. SQLite + BM25 uses negligible RAM. Vector embeddings are optional and can run on a separate service if needed.

### How External Knowledge Sources Fit In

```
Agent's Knowledge:
├── Built-in memory (sessions, daily notes, MEMORY.md, search index)
├── Skills (markdown knowledge files)
├── Notion (via MCP -- searches and reads your Notion workspace)
├── Obsidian (via MCP -- reads your vault directly)
├── Web (via search and fetch tools)
└── Other MCP servers (GitHub, email, calendar, etc.)
```

---

## 9. Deployment Architecture

### Your Situation

You have a ThinkPad X1 with an i5 processor. This machine:
- Works fine for **development and testing**
- Works fine for running nanobot with **cloud LLMs** (the AI runs on their servers, not yours)
- Is **not ideal for 24/7 always-on** operation (laptops aren't designed for this -- battery degradation, thermal throttling)
- Has **limited local AI performance** (Intel CPUs with Ollama are slow -- benchmarks show poor performance compared to AMD APUs)

### Recommended Setup

**Phase 1: Use your ThinkPad** (no cost)
- Run nanobot locally
- Use cloud LLMs (Anthropic, OpenAI)
- Access from work laptop via Cloudflare Tunnel
- This works for testing everything

**Phase 2: Dedicated mini PC for always-on** (when ready, ~$400-500)
- A small, silent, low-power computer that runs 24/7
- Runs nanobot + optionally a local small model
- Sits next to your router, always accessible

### Mini PC Recommendations

| Tier | Hardware | Best Model | Speed | Cost | Power |
|------|----------|-----------|-------|------|-------|
| Budget | Refurbished ThinkCentre (i5-8500T, 16GB DDR4) | Llama 3.2 3B | ~4 tok/s | $150-200 | 15-25W |
| **Sweet Spot** | **Beelink SER9 Pro (Ryzen 7 8845HS, 32GB DDR5)** | **Qwen 2.5 7B** | **10-15 tok/s** | **$400-500** | **10-45W** |
| Performance | Minisforum UM890 (Ryzen 9, 64GB DDR5) | Qwen 2.5 14B | 12-15 tok/s | $600-900 | 15-65W |
| Experiment | Raspberry Pi 5 (8GB) | Qwen 2.5 1.5B | 5-7 tok/s | $80 | 3-5W |

**Annual electricity cost for 24/7 operation**: $15-45 depending on tier (mostly idle, a personal assistant only generates tokens a few minutes per day).

The **sweet spot** recommendation is a Beelink SER9 Pro or Minisforum UM890 Pro. The AMD Ryzen APU with DDR5 memory gives usable speed with 7B models, and the iGPU shares system RAM efficiently with Ollama. Total first-year cost: ~$425-525 including electricity.

### Multi-Device Access

```
ALWAYS-ON SERVER (mini PC or ThinkPad)
├── nanobot gateway
├── Ollama (optional, for local models)
├── Cloudflare Tunnel (free, provides HTTPS)
│
├── From home:
│   └── Browser: http://localhost:18800
│
├── From work laptop (enterprise-restricted):
│   └── Browser: https://nanobot.yourdomain.com (via tunnel)
│       (Just a website - no app install, no VPN needed)
│
├── From Android phone:
│   ├── Browser: https://nanobot.yourdomain.com (PWA - "Add to Home Screen")
│   ├── Telegram: Message @your_nanobot_bot (native app experience)
│   └── (Future: lightweight app wrapper around the web UI)
│
└── From personal laptop:
    ├── Browser: https://nanobot.yourdomain.com
    └── CLI: nanobot agent (if nanobot is installed locally too)
```

### Android Access Options

1. **Telegram bot** (recommended for V1): Full native app experience, push notifications, voice messages. Already supported in nanobot. Just needs a Telegram bot token.
2. **Web PWA** ("Add to Home Screen"): Opens like an app, no install needed. Built in Phase 2.
3. **Lightweight app wrapper** (future): A simple Android app that wraps the web UI in a WebView for a more native feel. Low priority since Telegram and PWA cover the use case well.

### Security Layers

```
Internet
  --> Cloudflare (HTTPS, DDoS protection)
    --> Tunnel (encrypted connection to your server)
      --> nanobot web channel (token authentication)
        --> Agent (processes your request)
```

---

## 10. Technology Stack Summary

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.11+ | Simple, huge ecosystem, async support |
| AI Models | LiteLLM | Universal adapter for any AI provider |
| MCP Client | `mcp` (official SDK) | Connect to 5,800+ MCP tool servers |
| Web Server | aiohttp | Lightweight async HTTP + WebSocket |
| Config | Pydantic | Type-safe config with validation |
| HTTP Client | httpx | Async HTTP for APIs |
| CLI | Typer | Clean command-line interface |
| Logging | Loguru | Easy, readable logs |
| Memory Search | SQLite FTS5 | BM25 keyword search, zero dependencies |
| Scheduling | croniter | Cron expression support |
| Local AI | Ollama | Run local models (Qwen, Llama, Gemma, Phi) |
| Tunnel | Cloudflare | Free, secure remote access |
| PDF/Docs | WeasyPrint or similar | Create PDFs, read documents |

---

## 11. Extension Roadmap

### What Can Be Added (Roughly By Complexity)

| Capability | How | Notes |
|------------|-----|-------|
| Notion | MCP server (official, by Notion) | Config-only, no code needed |
| GitHub | MCP server (official) | Config-only |
| Obsidian | MCP server (community) | Config-only |
| Google Calendar | MCP server or tool plugin | Several community MCP servers exist |
| PDF creation/editing | Tool plugin (WeasyPrint or ReportLab) | Generate PDFs from markdown, read existing PDFs |
| PDF reading | Tool plugin (PyPDF2 or pdfplumber) | Extract text from PDFs for the agent |
| Email | Channel plugin (IMAP/SMTP) or MCP server | Gmail MCP server exists |
| NotebookLM | MCP server or API connector | When API becomes available |
| Image generation | MCP server or tool plugin (DALL-E/Flux) | Via OpenAI API |
| Spotify | MCP server (community) | Control playback, search music |
| Home automation | MCP server (Home Assistant) | Lights, thermostat, etc. |
| Slack | MCP server or channel plugin | Slack MCP servers exist |
| SMS | Tool plugin (Twilio) | Send/receive texts |
| Local model | Already supported | Configure Ollama in providers |
| RAG (document Q&A) | Memory system + vector embeddings | Build on SQLite + optional embeddings |
| Workflow automation | Chain tools into multi-step workflows | Via skills and subagents |
| Admin UI | Web page in web channel | Toggle plugins, manage config visually |
| Self-building tools | Meta-tool + skill-creator skill | Agent creates plugins with user approval |

### The Pattern: MCP First, Custom Second

For any new integration:
1. **Check if an MCP server exists** (most likely it does -- 5,800+ available)
2. If yes: **just add it to config** -- zero code, instant capability
3. If no: **build a custom tool plugin** following the Tool base class pattern
4. The agent can do steps 1-3 itself with the `create_tool` meta-tool

---

## 12. Glossary

| Term | Meaning |
|------|---------|
| **Channel** | A way to communicate with nanobot (web, Telegram, etc.) |
| **Message Bus** | Internal routing system (inbound and outbound message queues) |
| **Agent Loop** | The core processing engine that calls the AI and executes tools |
| **Tool** | An action the AI can take (search web, read file, etc.) |
| **Skill** | Procedural knowledge (how-to guides) loaded on demand into the agent's context |
| **MCP** | Model Context Protocol -- the universal standard for connecting AI to tools (like USB for AI) |
| **MCP Server** | An external service that provides tools via MCP (e.g., Notion MCP server) |
| **MCP Client** | The part of nanobot that connects to MCP servers and uses their tools |
| **Provider** | The AI model backend (Claude, GPT, Gemini, local model) |
| **Session** | Conversation history for a specific chat |
| **Plugin** | A self-contained, configurable extension (tool, channel, or skill) |
| **Subagent** | A background agent (often using a smaller model) spawned for a specific task |
| **Gateway mode** | Running nanobot as a server with all channels active |
| **Workspace** | The directory where agent config, memory, and skills live |
| **Compaction** | Summarizing old messages to free context space without losing information |
| **BM25** | A keyword search algorithm built into SQLite -- finds relevant text by matching words |
| **SLM** | Small Language Model -- a model small enough to run on your own hardware (1B-7B parameters) |
| **PWA** | Progressive Web App -- a website that behaves like a native app on your phone |
| **Ollama** | Software that runs AI models locally on your computer |
