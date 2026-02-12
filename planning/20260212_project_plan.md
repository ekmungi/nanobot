# Nanobot Project Plan

> **Location**: `C:/Users/ekmun/Dev/nanobot/PROJECT_PLAN.md`
> **Created**: 2026-02-11
> **Author**: Claude Code session with Anant
> **Status**: Planning complete, ready for implementation

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Current Architecture](#2-current-architecture)
3. [Implementation Tasks (Ordered by Effort)](#3-implementation-tasks)
   - [Task 1: .gitignore hardening](#task-1-gitignore-hardening-5-minutes)
   - [Task 2: Markdown rendering in web chat](#task-2-markdown-rendering-in-web-chat-1-2-hours)
   - [Task 3: Strategy router for design patterns](#task-3-strategy-router-for-design-patterns-half-day)
   - [Task 4: Within-chat memory summarization](#task-4-within-chat-memory-summarization-half-day)
   - [Task 5: SQLite migration for persistent memory](#task-5-sqlite-migration-for-persistent-memory-1-2-days)
4. [Architecture Decisions](#4-architecture-decisions)
5. [Files Already Modified (Prior Sessions)](#5-files-already-modified-prior-sessions)
6. [Library Versions & Dependencies](#6-library-versions--dependencies)
7. [Running & Testing](#7-running--testing)
8. [Key Context for Future Sessions](#8-key-context-for-future-sessions)

---

## 1. Project Overview

**Nanobot** is a personal AI assistant framework. The user (Anant) works in medical AI/R&D and uses this to interface with Notion for meetings, project tracking, and notes.

**Stack**: Python 3.11+ | LiteLLM (OpenRouter) | MCP (Notion) | aiohttp (web channel) | JSONL (sessions)

**Current model**: `openrouter/openai/gpt-5-nano`

**Config location**: `~/.nanobot/config.json` (outside repo, safe from git)

**Architecture**:
```
User Message -> Channel (web/cli/telegram)
    -> MessageBus -> AgentLoop
        -> ContextBuilder (system prompt + skills + history)
        -> LLMProvider.chat() (via LiteLLM)
        -> ToolRegistry.execute() (tools including MCP wrappers)
        -> Response -> Channel
```

---

## 2. Current Architecture

### Core Files

| File | Purpose | Lines |
|------|---------|-------|
| `nanobot/agent/loop.py` | Agent loop, tool execution, MCP init | ~477 |
| `nanobot/agent/context.py` | System prompt + skills + history assembly | ~204 |
| `nanobot/agent/tools/registry.py` | Tool registry, fuzzy matching, URL intercepts | ~191 |
| `nanobot/session/manager.py` | JSONL session storage, 50-message cap | ~203 |
| `nanobot/channels/web.py` | WebSocket chat channel | ~186 |
| `nanobot/channels/web_static/index.html` | Chat UI (single HTML file) | ~200 |
| `nanobot/mcp/wrappers/notion.py` | 5 semantic Notion tools, response compression | ~950 |
| `nanobot/providers/litellm_provider.py` | LLM provider, 120s timeout | ~224 |
| `nanobot/config/schema.py` | Pydantic config models | ~198 |
| `nanobot/config/loader.py` | JSON config loading, camelCase conversion | ~124 |

### Session/Memory Architecture (Current)

- **Storage**: JSONL files at `~/.nanobot/sessions/{channel}_{chat_id}.jsonl`
- **Format**: First line = metadata JSON, subsequent lines = message JSON objects
- **History limit**: 50 messages (hardcoded default in `Session.get_history()`)
- **LLM context**: Only `role` + `content` sent to LLM (timestamps stripped)
- **Cache**: In-memory dict in `SessionManager._cache`
- **No summarization**: Hard cutoff at 50 messages, older messages silently dropped
- **No cross-chat memory**: Each session is isolated
- **No token counting**: Hopes 50 messages fit in context window

### Web Chat UI (Current)

- Single HTML file with inline CSS/JS
- Custom `formatMarkdown()` function supports only: code blocks, inline code, bold, italic
- **Missing**: Headers, lists, tables, links, blockquotes, syntax highlighting
- **XSS vulnerability**: Uses `innerHTML` without sanitization
- Plain textarea input (no markdown preview)

### Agent Design Pattern (Current)

Single ReAct loop for all tasks:
```
Think -> Act (tool call) -> Observe (result) -> Repeat (up to max_iterations)
```

No task classification, no planning phase, no progressive disclosure.

---

## 3. Implementation Tasks

Ordered by effort (lowest first), as requested by user.

---

### Task 1: .gitignore Hardening (~5 minutes)

**Priority**: Low | **Effort**: Trivial | **Risk**: None

**What**: Add `config.json` and `*.secret` to `.gitignore` as defense-in-depth.

**Current state**: Config is already safe (lives at `~/.nanobot/` outside repo). No real API keys in git history. This is purely a safety net.

**Changes**:

| File | Change |
|------|--------|
| `.gitignore` | Add `config.json`, `*.secret`, `*.key` entries |

**Implementation**:
```
# Add to .gitignore:
config.json
*.secret
*.key
```

**Verification**: `git status` should not show any new untracked config files.

---

### Task 2: Markdown Rendering in Web Chat (~1-2 hours)

**Priority**: High | **Effort**: Small | **Risk**: Low

**What**: Replace the custom `formatMarkdown()` with proper markdown rendering using `marked.js` + `DOMPurify` + `highlight.js`. Fix XSS vulnerability.

**Why marked.js**: It's the most popular markdown parser (57K+ GitHub stars), actively maintained, and lightweight. The alternative (markdown-it) is also good but marked.js has simpler API for this use case.

**Current state**: `nanobot/channels/web_static/index.html` has a 10-line regex-based `formatMarkdown()` that only handles code blocks, inline code, bold, and italic. Bot messages use `innerHTML` without sanitization.

**Changes**:

| File | Change |
|------|--------|
| `nanobot/channels/web_static/index.html` | Add CDN scripts, replace `formatMarkdown()`, add CSS for markdown elements |

**Libraries to add (via CDN, no server-side changes needed)**:

| Library | Version | CDN URL | Purpose |
|---------|---------|---------|---------|
| marked.js | 17.x | `https://cdn.jsdelivr.net/npm/marked/marked.min.js` | Markdown parsing |
| DOMPurify | 3.x | `https://cdn.jsdelivr.net/npm/dompurify/dist/purify.min.js` | XSS sanitization |
| highlight.js | 11.x | `https://cdn.jsdelivr.net/gh/highlightjs/cdn-release/build/highlight.min.js` | Code syntax highlighting |

> **Note on versioning**: Use `marked` not `marked@17.0.1` in CDN URLs so it auto-resolves to latest minor/patch. Pin major version only if breaking changes are a concern. The `@latest` approach avoids the stale-library problem the user encountered with the Notion API.

**Implementation details**:

1. **Add CDN scripts** to `<head>`:
   ```html
   <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
   <script src="https://cdn.jsdelivr.net/npm/dompurify/dist/purify.min.js"></script>
   <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release/build/styles/github-dark.min.css">
   <script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release/build/highlight.min.js"></script>
   ```

2. **Replace `formatMarkdown()` function** (line 156-166 of index.html):
   ```javascript
   function formatMarkdown(text) {
     const html = marked.parse(text);
     return DOMPurify.sanitize(html);
   }
   ```

3. **Configure marked** for code highlighting:
   ```javascript
   marked.setOptions({
     highlight: function(code, lang) {
       if (lang && hljs.getLanguage(lang)) {
         return hljs.highlight(code, { language: lang }).value;
       }
       return hljs.highlightAuto(code).value;
     },
     breaks: true,  // GFM line breaks
     gfm: true,     // GitHub Flavored Markdown (tables, strikethrough, etc.)
   });
   ```

4. **Add CSS** for rendered markdown elements:
   ```css
   .msg.bot h1, .msg.bot h2, .msg.bot h3 { margin: 12px 0 6px; }
   .msg.bot h1 { font-size: 1.3em; }
   .msg.bot h2 { font-size: 1.15em; }
   .msg.bot h3 { font-size: 1.05em; }
   .msg.bot ul, .msg.bot ol { padding-left: 20px; margin: 6px 0; }
   .msg.bot li { margin: 2px 0; }
   .msg.bot table { border-collapse: collapse; margin: 8px 0; width: 100%; }
   .msg.bot th, .msg.bot td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; }
   .msg.bot th { background: var(--surface2); }
   .msg.bot blockquote { border-left: 3px solid var(--accent); padding-left: 12px; color: var(--text-dim); margin: 8px 0; }
   .msg.bot a { color: var(--accent); text-decoration: none; }
   .msg.bot a:hover { text-decoration: underline; }
   .msg.bot hr { border: none; border-top: 1px solid var(--border); margin: 12px 0; }
   .msg.bot p { margin: 4px 0; }
   ```

5. **Remove `white-space: pre-wrap`** from `.msg.bot` CSS (line 30) since marked.js handles whitespace via `<p>` tags. Keep it for `.msg.user`.

6. **Input box**: Keep as plain textarea. Claude Code itself uses plain text input. Markdown rendering is only for output. This avoids the complexity of a WYSIWYG editor.

**Verification**:
- Send a message from the LLM containing headers, lists, tables, code blocks
- Verify proper rendering
- Test XSS: confirm `<script>alert('xss')</script>` in bot response is sanitized
- Test code block syntax highlighting

---

### Task 3: Strategy Router for Design Patterns (~half day)

**Priority**: Medium | **Effort**: Medium | **Risk**: Medium

**What**: Add the ability for the agent to choose different reasoning strategies based on task complexity, instead of always running the same ReAct loop.

**Background**: Currently, the agent in `loop.py` always follows the same pattern: call LLM -> execute tools -> repeat. This works for simple lookups but fails for complex multi-step tasks where `gpt-5-nano` doesn't have the reasoning depth to plan well.

Claude Code solves this by having explicit modes (plan mode, explore mode, execute mode) and specialized sub-agents. We can adapt this without the full complexity.

**Approach: Skill-based strategy hints + plan tool**

Rather than adding a pre-classification LLM call (which costs tokens and latency), we teach the LLM about strategies via a skill and give it a `plan` tool to self-organize.

**Changes**:

| File | Change |
|------|--------|
| `nanobot/skills/strategies/SKILL.md` | **NEW** - Skill teaching the LLM about strategy patterns |
| `nanobot/agent/tools/plan.py` | **NEW** - Plan tool for structured task decomposition |
| `nanobot/agent/loop.py` | Register `PlanTool`, minor changes |

**New file: `nanobot/skills/strategies/SKILL.md`**
```markdown
---
name: strategies
description: Task strategy patterns
always: true
---

# Task Strategy Guide

Before responding, consider which strategy fits this task:

## Quick Answer
For simple questions, factual lookups, or single-tool tasks.
Just respond directly. No planning needed.

## Lookup & Respond
For tasks requiring 1-2 tool calls (search, read a page, etc.).
Call the tool, then summarize the result.

## Multi-Step Execution
For tasks requiring 3+ steps or multiple tools.
Use the `plan` tool first to outline your steps, then execute them one by one.

## Research & Synthesize
For open-ended questions requiring information from multiple sources.
Search broadly first, then read specific results, then synthesize.

Choose the simplest strategy that fits. Don't over-plan simple tasks.
```

**New file: `nanobot/agent/tools/plan.py`**
```python
"""Plan tool for structured task decomposition."""

from nanobot.agent.tools.base import Tool


class PlanTool(Tool):
    """Create a step-by-step plan before executing complex tasks."""

    name = "plan"
    description = (
        "Create a step-by-step plan for complex tasks. "
        "Use this when a task requires 3+ steps. "
        "Input: task description and list of steps. "
        "Output: formatted plan for reference."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "What you are trying to accomplish"
            },
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered list of steps to complete the task"
            }
        },
        "required": ["task", "steps"]
    }

    async def execute(self, **kwargs) -> str:
        task = kwargs.get("task", "")
        steps = kwargs.get("steps", [])

        lines = [f"Plan: {task}", ""]
        for i, step in enumerate(steps, 1):
            lines.append(f"  {i}. {step}")
        lines.append("")
        lines.append("Execute each step in order. Mark steps complete as you go.")
        return "\n".join(lines)
```

**Changes to `nanobot/agent/loop.py`**:
```python
# Add import
from nanobot.agent.tools.plan import PlanTool

# In _register_default_tools():
self.tools.register(PlanTool())
```

**Why this approach over a pre-classifier**:
- No extra LLM call (saves tokens and latency)
- The skill teaches the LLM to self-classify
- The plan tool gives it structure when needed
- Works with any model (not dependent on specific classifier behavior)
- Easy to extend: add new strategies by editing the skill file

**Verification**:
- Simple question ("What time is it?") -> agent responds directly, no plan tool call
- Complex question ("Find all my meetings this week and summarize them") -> agent uses plan tool first
- Check that plan tool output appears in logs

---

### Task 4: Within-Chat Memory Summarization (~half day)

**Priority**: High | **Effort**: Medium | **Risk**: Medium

**What**: When conversation history approaches the token/message limit, automatically summarize older messages into a compact block instead of silently dropping them.

**Current state**: `Session.get_history(max_messages=50)` returns the last 50 messages. Older messages are invisible to the LLM. No token counting.

**Approach: Rolling summary with token budgeting**

**Changes**:

| File | Change |
|------|--------|
| `nanobot/session/manager.py` | Add `get_context_history()` with summarization, add token estimation |
| `nanobot/agent/loop.py` | Use `get_context_history()` instead of `get_history()`, pass provider for summarization |
| `nanobot/agent/context.py` | Accept summary prefix in `build_messages()` |

**Implementation details**:

1. **Token estimation** (simple, no external dependency):
   ```python
   def _estimate_tokens(self, text: str) -> int:
       """Rough token estimate: ~4 chars per token for English."""
       return len(text) // 4
   ```

2. **Rolling summary** in `Session`:
   ```python
   def get_context_history(
       self,
       max_tokens: int = 6000,
       summarizer: Callable | None = None,
   ) -> list[dict]:
       """Get history with automatic summarization for older messages.

       Returns recent messages that fit in max_tokens budget.
       If there are older messages, prepends a summary.
       """
       # Start from most recent, work backwards
       recent = []
       token_count = 0

       for msg in reversed(self.messages):
           msg_tokens = self._estimate_tokens(msg["content"])
           if token_count + msg_tokens > max_tokens * 0.8:  # 80% for messages
               break
           recent.insert(0, {"role": msg["role"], "content": msg["content"]})
           token_count += msg_tokens

       # If we have older messages, add summary
       included_count = len(recent)
       total_count = len(self.messages)

       if included_count < total_count and self._summary:
           summary_msg = {
               "role": "system",
               "content": f"[Summary of earlier conversation ({total_count - included_count} messages)]: {self._summary}"
           }
           recent.insert(0, summary_msg)

       return recent
   ```

3. **Summary generation** (triggered when messages exceed threshold):
   ```python
   async def _generate_summary(self, provider, model, messages_to_summarize):
       """Ask the LLM to summarize older messages."""
       prompt = [
           {"role": "system", "content": "Summarize this conversation concisely. Include key facts, decisions, and context needed to continue the conversation. Max 200 words."},
           {"role": "user", "content": "\n".join(
               f"{m['role']}: {m['content']}" for m in messages_to_summarize
           )}
       ]
       response = await provider.chat(messages=prompt, model=model, max_tokens=300)
       return response.content
   ```

4. **When to trigger summarization**:
   - When `len(self.messages) > 40` and no existing summary
   - When `len(self.messages) > 80` (re-summarize with more context)
   - Summary is stored in session metadata (persisted to JSONL)

**Important design note**: The summary is stored in the session's metadata dict (already supported by the JSONL format). This means no schema change is needed.

**Verification**:
- Create a session with 60+ messages
- Verify that `get_context_history()` returns a summary prefix + recent messages
- Verify the summary persists across restarts (saved in JSONL metadata)
- Verify token count stays within budget

---

### Task 5: SQLite Migration for Persistent Memory (~1-2 days)

**Priority**: Medium | **Effort**: Large | **Risk**: Medium-High

**What**: Migrate from JSONL files to SQLite for conversation storage, enabling cross-chat search, better querying, and a foundation for cross-chat memory.

**Why SQLite**:
- Python stdlib (`sqlite3`) — no new dependency
- Single file, portable, easy to backup
- FTS5 for full-text search across conversations
- WAL mode for concurrent reads
- Scales to millions of messages without performance issues
- Well-tested, battle-hardened (used by every browser, phone, etc.)

**Current state**: JSONL files at `~/.nanobot/sessions/`. Each file is one conversation. No search capability across conversations.

**Approach: Phased migration with dual-write**

### Phase 1: Add SQLite alongside JSONL (dual-write)

**Changes**:

| File | Change |
|------|--------|
| `nanobot/session/store.py` | **NEW** - SQLite storage backend |
| `nanobot/session/manager.py` | Add dual-write to SQLite, keep JSONL as primary |
| `pyproject.toml` | No changes (sqlite3 is stdlib) |

**Schema** (`~/.nanobot/nanobot.db`):

```sql
-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,              -- "channel:chat_id"
    channel TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    created_at TEXT NOT NULL,         -- ISO 8601
    updated_at TEXT NOT NULL,
    summary TEXT,                     -- rolling conversation summary
    metadata TEXT                     -- JSON blob for extensibility
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,               -- user/assistant/system/tool
    content TEXT NOT NULL,
    tool_calls TEXT,                  -- JSON blob (optional)
    token_estimate INTEGER,           -- rough token count
    created_at TEXT NOT NULL,         -- ISO 8601
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);

-- Full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content=messages,
    content_rowid=id
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
```

**New file: `nanobot/session/store.py`**

```python
"""SQLite storage backend for conversations and messages."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ConversationStore:
    """SQLite-backed conversation storage with FTS5 search."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def close(self) -> None:
        if self._conn:
            self._conn.close()

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        # Execute the schema SQL above
        ...

    def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: list | None = None,
    ) -> int:
        """Save a message and return its ID."""
        ...

    def get_history(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get recent messages for a conversation."""
        ...

    def search(
        self,
        query: str,
        conversation_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Full-text search across conversations."""
        cursor = self._conn.execute(
            """
            SELECT m.*, c.channel, c.chat_id
            FROM messages_fts fts
            JOIN messages m ON m.id = fts.rowid
            JOIN conversations c ON c.id = m.conversation_id
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        return [dict(row) for row in cursor.fetchall()]
```

### Phase 2: Switch primary storage to SQLite

Once dual-write is stable:
- Change `SessionManager` to read from SQLite (instead of JSONL)
- Keep JSONL write for backward compatibility / human-readable backup
- Add migration script to import existing JSONL sessions into SQLite

### Phase 3: Add cross-chat memory

**New table for persistent memory**:
```sql
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,           -- "fact", "preference", "decision", "context"
    key TEXT,                         -- searchable topic/tag
    content TEXT NOT NULL,
    source_conversation TEXT,         -- conversation ID where this was learned
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    relevance_score REAL DEFAULT 1.0  -- for retrieval ranking (decays over time)
);

CREATE INDEX IF NOT EXISTS idx_memory_category ON memory(category);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(key, content, content=memory, content_rowid=id);
```

**New tool: `remember`**:
```python
class RememberTool(Tool):
    """Store a fact or insight for future conversations."""
    name = "remember"
    description = "Save important information for future reference across conversations."
    parameters = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["fact", "preference", "decision", "context"]},
            "key": {"type": "string", "description": "Short topic label"},
            "content": {"type": "string", "description": "The information to remember"},
        },
        "required": ["key", "content"]
    }
```

**New tool: `recall`**:
```python
class RecallTool(Tool):
    """Search persistent memory and past conversations."""
    name = "recall"
    description = "Search your memory and past conversations for relevant information."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for"},
        },
        "required": ["query"]
    }
```

### Phase 4: Remove JSONL (optional, future)

Only after SQLite is proven stable. JSONL files can be archived or kept as human-readable backups.

**Verification for each phase**:
- Phase 1: Verify dual-write works, SQLite file created, FTS search returns results
- Phase 2: Verify sessions load from SQLite, backward compat with existing JSONL
- Phase 3: Verify `remember` and `recall` tools work across separate conversations
- Phase 4: Verify JSONL removal doesn't break anything

---

## 4. Architecture Decisions

### Decision 1: CDN-loaded JS libraries (not bundled)

**Rationale**: The web UI is a single HTML file served by aiohttp. Adding a build pipeline (webpack, vite) would be over-engineering for 3 JS libraries. CDN loading is simpler, always gets latest patches, and the user specifically asked to avoid stale library versions.

**Trade-off**: Requires internet connectivity for the web UI. If offline usage is needed later, bundle the libraries.

### Decision 2: Skill-based strategy routing (not pre-classifier)

**Rationale**: Adding a pre-classification LLM call doubles latency and token cost for every message. Instead, teach the LLM about strategies via an always-loaded skill. The LLM self-classifies based on the skill's guidance. This is how Claude Code uses skills for mode selection.

**Trade-off**: Less deterministic than a classifier. The LLM may not always choose the optimal strategy. But it's free (no extra API calls) and can be refined by editing the skill file.

### Decision 3: SQLite over Postgres/external DB

**Rationale**: Nanobot is a personal assistant running on a single machine. SQLite handles concurrent reads via WAL mode, requires zero setup (stdlib), and stores everything in one file. Postgres would be over-engineering.

**Trade-off**: SQLite doesn't support concurrent writes from multiple processes. If multi-process deployment is needed later, consider switching to Postgres or adding a write queue.

### Decision 4: Token estimation via character count (not tokenizer)

**Rationale**: Using `tiktoken` or a proper tokenizer adds a dependency and complexity. The ~4 chars/token heuristic is well-known and sufficient for budgeting (it slightly over-counts, which is safer than under-counting).

**Trade-off**: Inaccurate for non-English text or code-heavy content. Can upgrade to `tiktoken` later if needed.

### Decision 5: Dual-write migration (not big-bang switch)

**Rationale**: Switching storage backends is risky. Dual-write (JSONL + SQLite) during migration lets us validate SQLite is correct before switching reads. If SQLite has issues, JSONL is still there.

---

## 5. Files Already Modified (Prior Sessions)

These files were modified in previous Claude Code sessions (visible in `git status`):

| File | What Changed | Why |
|------|-------------|-----|
| `nanobot/__init__.py` | Version bump | Standard release management |
| `nanobot/agent/context.py` | Context builder improvements | Support for skills, memory, media |
| `nanobot/agent/loop.py` | MCP integration, `max_tokens` passthrough, error handling | Core feature: MCP tools, LLM reliability |
| `nanobot/agent/skills.py` | Skill loading with frontmatter | Support always-loaded skills |
| `nanobot/agent/tools/registry.py` | Fuzzy matching, URL interception | Handle LLM hallucinated tool names, Notion URL redirect |
| `nanobot/channels/manager.py` | Channel manager updates | Web channel support |
| `nanobot/cli/commands.py` | Gateway command, Windows UTF-8 fix | Full server startup, Windows compat |
| `nanobot/config/loader.py` | `_PRESERVE_VALUE_KEYS` for env vars | Fix: prevent `NOTION_TOKEN` -> `n_o_t_i_o_n__t_o_k_e_n` |
| `nanobot/config/schema.py` | `MCPServerConfig.semantic_wrappers` field | Config for MCP wrapper mode |
| `nanobot/providers/litellm_provider.py` | 120s timeout, `max_tokens` passthrough | Fix: LLM hanging, token budget |
| `pyproject.toml` | Dependencies: `mcp`, `aiohttp`, `croniter` | MCP integration, web channel, scheduling |

**New files created in prior sessions** (untracked):

| File | Purpose |
|------|---------|
| `nanobot/channels/web.py` | WebSocket-based web chat channel |
| `nanobot/channels/web_static/index.html` | Single-page chat UI |
| `nanobot/mcp/` (entire directory) | MCP client, bridge, and semantic wrappers |
| `nanobot/skills/notion-tools/SKILL.md` | Always-loaded Notion tool usage guide |
| `nanobot/skills/filesystem-tools/SKILL.md` | Filesystem tool guide |
| `.claude/` | Claude Code project config and memory |

---

## 6. Library Versions & Dependencies

### Current Python Dependencies (`pyproject.toml`)

| Package | Version Constraint | Purpose |
|---------|-------------------|---------|
| typer | >=0.9.0 | CLI framework |
| litellm | >=1.0.0 | LLM provider abstraction |
| pydantic | >=2.0.0 | Data validation |
| pydantic-settings | >=2.0.0 | Settings management |
| loguru | >=0.7.0 | Logging |
| aiohttp | >=3.9.0 | Web channel HTTP/WS |
| mcp | >=1.0.0 | Model Context Protocol |
| httpx | >=0.25.0 | HTTP client |
| croniter | >=2.0.0 | Cron scheduling |
| rich | >=13.0.0 | Terminal formatting |
| websockets | >=12.0 | WebSocket client |

### New Dependencies Needed

| Package | Type | Version | Purpose | Task |
|---------|------|---------|---------|------|
| marked.js | JS (CDN) | 17.x | Markdown rendering | Task 2 |
| DOMPurify | JS (CDN) | 3.x | XSS sanitization | Task 2 |
| highlight.js | JS (CDN) | 11.x | Code syntax highlighting | Task 2 |
| sqlite3 | Python stdlib | (built-in) | Persistent storage | Task 5 |

**No new Python dependencies required for any task.** SQLite is in the standard library.

### Version Pinning Strategy

Per user's request to avoid stale libraries:
- **Python packages**: Use `>=X.0.0` (minimum version, auto-upgrades on install)
- **JS CDN**: Use `https://cdn.jsdelivr.net/npm/marked/marked.min.js` (no version pin = latest)
- **Periodically audit**: Check for major version bumps that may require code changes

---

## 7. Running & Testing

### Start the full server
```bash
uv run python -m nanobot gateway
```
This starts: web channel (port 18800), gateway API (port 18790), agent loop, MCP connections.

### Direct agent interaction
```bash
uv run python -m nanobot agent -m "Search my Notion for meetings"
```

### Run tests
```bash
uv run python tests/test_mcp_notion.py
uv run python tests/test_tool_validation.py
```

> **Note**: No pytest installed. Tests use direct `uv run python tests/test_file.py`. The `tests/` directory is in `.gitignore`.

### Web UI access
Navigate to `http://localhost:18800` after starting the gateway.

---

## 8. Key Context for Future Sessions

### Things a fresh session MUST know:

1. **Windows environment**: Use `uv run python` not bare `python`. Paths use `C:/` not `/`.

2. **Config is external**: `~/.nanobot/config.json` is NOT in the repo. It contains API keys. Never try to read it from the repo.

3. **MCP is the most complex subsystem**: The Notion MCP integration has two modes (remote/local), semantic wrappers that compress responses, and several known edge cases (calendar IDs not fetchable, database URL vs object ID mismatch). Read `MEMORY.md` for full details.

4. **The web UI is a single HTML file**: All CSS and JS are inline in `nanobot/channels/web_static/index.html`. No build pipeline.

5. **Session storage is JSONL**: Files at `~/.nanobot/sessions/`. First line is metadata, rest are messages. The `Session` class is a dataclass with `get_history(max_messages=50)`.

6. **The agent loop is in `loop.py`**: It's a while loop that calls the LLM, executes tool calls, and repeats until no more tool calls or max iterations (20) reached.

7. **Skills are markdown files**: Loaded from `nanobot/skills/<name>/SKILL.md`. Frontmatter with `always: true` means always loaded into system prompt.

8. **Tool calls are persisted in history**: But only `role` + `content` are sent back to the LLM on next turn. Tool call details are lost between turns.

9. **Implementation order matters**: Do tasks in order (1-5). Each task is independent but builds toward the same goal of a more capable agent.

10. **User preferences**: Anant wants scalable, modern architecture. Avoid stale library versions. Prefer latest stable releases. Don't over-engineer but design for extensibility.

### Memory files location
- **Claude Code memory**: `C:\Users\ekmun\.claude\projects\C--Users-ekmun-Dev-nanobot\memory\MEMORY.md`
- **This plan**: `C:\Users\ekmun\Dev\nanobot\PROJECT_PLAN.md`

---

## Implementation Checklist

- [ ] **Task 1**: Add `config.json` to `.gitignore` (~5 min)
- [ ] **Task 2**: Markdown rendering with marked.js + DOMPurify + highlight.js (~1-2 hrs)
- [ ] **Task 3**: Strategy skill + plan tool (~half day)
- [ ] **Task 4**: Within-chat summarization + token budgeting (~half day)
- [ ] **Task 5 Phase 1**: SQLite dual-write alongside JSONL (~1 day)
- [ ] **Task 5 Phase 2**: Switch reads to SQLite (~half day)
- [ ] **Task 5 Phase 3**: Cross-chat memory tools (remember/recall) (~1 day)
- [ ] **Task 5 Phase 4**: Remove JSONL (optional, future)
