"""Tests for PROJECT_PLAN.md implementation tasks.

Tests Tasks 1-5: .gitignore, markdown UI, plan tool, summarization, SQLite store,
memory tools.
"""

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path

# ── Test helpers ──

PASS = 0
FAIL = 0


def ok(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Task 1: .gitignore ──

def test_gitignore():
    section("Task 1: .gitignore hardening")
    gitignore = Path(__file__).parent.parent / ".gitignore"
    content = gitignore.read_text()
    ok("config.json in .gitignore", "config.json" in content)
    ok("*.secret in .gitignore", "*.secret" in content)
    ok("*.key in .gitignore", "*.key" in content)


# ── Task 2: Markdown rendering ──

def test_web_ui_markdown():
    section("Task 2: Web UI markdown rendering")
    html_path = Path(__file__).parent.parent / "nanobot" / "channels" / "web_static" / "index.html"
    content = html_path.read_text()

    ok("marked.js CDN loaded", "marked/marked.min.js" in content)
    ok("DOMPurify CDN loaded", "dompurify" in content.lower())
    ok("highlight.js CDN loaded", "highlight.min.js" in content)
    ok("highlight.js CSS loaded", "github-dark.min.css" in content)
    ok("formatMarkdown uses marked.parse", "marked.parse" in content)
    ok("formatMarkdown uses DOMPurify.sanitize", "DOMPurify.sanitize" in content)
    ok("marked.setOptions configured", "marked.setOptions" in content)
    ok("GFM enabled", "gfm: true" in content)
    ok("No old regex formatMarkdown", "text.replace(/```" not in content)
    ok("XSS protection via DOMPurify", "DOMPurify" in content)
    ok("Bot markdown CSS for tables", ".msg.bot table" in content)
    ok("Bot markdown CSS for blockquotes", ".msg.bot blockquote" in content)
    ok("Bot markdown CSS for headers", ".msg.bot h1" in content)
    ok("Bot markdown CSS for lists", ".msg.bot ul" in content)
    ok("User messages keep pre-wrap", "msg.user" in content and "pre-wrap" in content)


# ── Task 3: Strategy skill + plan tool ──

def test_strategy_skill():
    section("Task 3a: Strategy skill")
    skill_path = Path(__file__).parent.parent / "nanobot" / "skills" / "strategies" / "SKILL.md"
    ok("Strategy skill file exists", skill_path.exists())
    content = skill_path.read_text()
    ok("Skill has frontmatter", content.startswith("---"))
    ok("always: true in frontmatter", "always: true" in content)
    ok("Quick Answer strategy", "Quick Answer" in content)
    ok("Multi-Step strategy", "Multi-Step" in content)
    ok("Research & Synthesize strategy", "Research & Synthesize" in content)


def test_plan_tool():
    section("Task 3b: Plan tool")
    from nanobot.agent.tools.plan import PlanTool

    tool = PlanTool()
    ok("Plan tool name is 'plan'", tool.name == "plan")
    ok("Plan tool has description", len(tool.description) > 10)
    ok("Plan tool requires 'task' param", "task" in tool.parameters.get("required", []))
    ok("Plan tool requires 'steps' param", "steps" in tool.parameters.get("required", []))

    # Test execution
    result = asyncio.run(tool.execute(task="Test task", steps=["Step 1", "Step 2", "Step 3"]))
    ok("Plan output contains task", "Test task" in result)
    ok("Plan output contains steps", "1. Step 1" in result)
    ok("Plan output contains step 3", "3. Step 3" in result)

    # Test schema
    schema = tool.to_schema()
    ok("Schema type is function", schema["type"] == "function")
    ok("Schema has name", schema["function"]["name"] == "plan")


# ── Task 4: Session summarization ──

def test_session_summarization():
    section("Task 4: Session summarization")
    from nanobot.session.manager import Session

    # Test token estimation
    session = Session(key="test:summarization")
    ok("_estimate_tokens exists", hasattr(session, '_estimate_tokens'))
    ok("Token estimate ~4 chars/token", Session._estimate_tokens("hello world test") == 4)

    # Test needs_summarization
    session_short = Session(key="test:short")
    for i in range(20):
        session_short.add_message("user", f"Message {i}")
    ok("Short session doesn't need summarization", not session_short.needs_summarization())

    session_long = Session(key="test:long")
    for i in range(45):
        session_long.add_message("user", f"Message {i}")
    ok("Long session (45 msgs) needs summarization", session_long.needs_summarization())

    # Test with existing summary
    session_with_summary = Session(key="test:summarized", metadata={"summary": "Test summary"})
    for i in range(45):
        session_with_summary.add_message("user", f"Message {i}")
    ok("Session with summary doesn't re-summarize at 45", not session_with_summary.needs_summarization())

    session_very_long = Session(key="test:very_long", metadata={"summary": "Test summary"})
    for i in range(85):
        session_very_long.add_message("user", f"Message {i}")
    ok("Very long session (85 msgs) re-summarizes", session_very_long.needs_summarization())

    # Test get_context_history (use long messages so they exceed token budget)
    session_ctx = Session(key="test:ctx")
    for i in range(60):
        session_ctx.add_message("user", f"This is a longer message number {i} with enough content to consume tokens " * 3)
    session_ctx.metadata["summary"] = "Earlier conversation summary"

    history = session_ctx.get_context_history(max_tokens=500)
    ok("Context history is a list", isinstance(history, list))
    ok("Context history has messages", len(history) > 0)
    # Check summary prefix
    has_summary_msg = any(
        m.get("role") == "system" and "Summary of earlier" in m.get("content", "")
        for m in history
    )
    ok("Context history includes summary prefix", has_summary_msg)

    # Test get_messages_to_summarize
    msgs = session_ctx.get_messages_to_summarize()
    ok("Messages to summarize returns first half", len(msgs) == 30)


# ── Task 5 Phase 1: SQLite store ──

def test_sqlite_store():
    section("Task 5 Phase 1: SQLite store")
    from nanobot.session.store import ConversationStore

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = ConversationStore(db_path)
        store.connect()

        ok("Database file created", db_path.exists())

        # Test conversation creation
        store.ensure_conversation("test:chat1", "test", "chat1")
        ok("Conversation created", True)

        # Test message saving
        msg_id = store.save_message("test:chat1", "user", "Hello world")
        ok("Message saved with ID", msg_id > 0)

        msg_id2 = store.save_message("test:chat1", "assistant", "Hi there!")
        ok("Second message saved", msg_id2 > msg_id)

        # Test history retrieval
        history = store.get_history("test:chat1")
        ok("History returns messages", len(history) == 2)
        ok("First message is user", history[0]["role"] == "user")
        ok("Second message is assistant", history[1]["role"] == "assistant")
        ok("Content preserved", history[0]["content"] == "Hello world")

        # Test message count
        count = store.get_message_count("test:chat1")
        ok("Message count is 2", count == 2)

        # Test FTS search
        results = store.search("Hello")
        ok("FTS finds 'Hello'", len(results) > 0)
        ok("FTS result has correct content", results[0]["content"] == "Hello world")

        results2 = store.search("nonexistent_xyz")
        ok("FTS returns empty for no match", len(results2) == 0)

        # Test conversation summary
        store.update_conversation_summary("test:chat1", "Test summary")
        summary = store.get_conversation_summary("test:chat1")
        ok("Summary stored and retrieved", summary == "Test summary")

        # Test token estimate
        ok("Token estimate works", store._estimate_tokens("test") == 1)

        store.close()
        ok("Store closed without error", True)


# ── Task 5 Phase 2: Dual-write in SessionManager ──

def test_session_manager_dual_write():
    section("Task 5 Phase 2: SessionManager dual-write")
    from nanobot.session.manager import SessionManager

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()

        # Patch sessions_dir and db_path for testing
        manager = SessionManager(workspace)
        manager.sessions_dir = Path(tmpdir) / "sessions"
        manager.sessions_dir.mkdir()

        # Override store to use temp DB
        from nanobot.session.store import ConversationStore
        db_path = Path(tmpdir) / "test.db"
        manager._store = ConversationStore(db_path)
        manager._store.connect()

        # Test get_or_create
        session = manager.get_or_create("web:user123")
        ok("Session created", session.key == "web:user123")

        # Add messages and save
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there")
        manager.save(session)

        # Verify JSONL was written
        jsonl_files = list(manager.sessions_dir.glob("*.jsonl"))
        ok("JSONL file created", len(jsonl_files) == 1)

        # Verify SQLite was written
        store = manager._store
        count = store.get_message_count("web:user123")
        ok("SQLite has 2 messages", count == 2)

        history = store.get_history("web:user123")
        ok("SQLite history matches", len(history) == 2)
        ok("SQLite first msg content", history[0]["content"] == "Hello")

        # Test that re-saving doesn't duplicate
        session.add_message("user", "Another message")
        manager.save(session)
        count2 = store.get_message_count("web:user123")
        ok("No duplicates on re-save", count2 == 3)

        manager._store.close()


# ── Task 5 Phase 3: Memory tools ──

def test_memory_tools():
    section("Task 5 Phase 3: Memory tools (remember/recall)")
    from nanobot.agent.tools.memory_tools import RememberTool, RecallTool
    from nanobot.session.store import ConversationStore

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = ConversationStore(db_path)
        store.connect()

        # Test RememberTool
        remember = RememberTool(store=store)
        ok("RememberTool name is 'remember'", remember.name == "remember")
        ok("RememberTool has parameters", "key" in str(remember.parameters))

        result = asyncio.run(remember.execute(
            key="user_name",
            content="The user's name is Anant",
            category="fact",
        ))
        ok("Remember returns confirmation", "Remembered" in result)

        # Test RecallTool
        recall = RecallTool(store=store)
        ok("RecallTool name is 'recall'", recall.name == "recall")

        result = asyncio.run(recall.execute(query="Anant"))
        ok("Recall finds the memory", "Anant" in result)
        ok("Recall shows category", "fact" in result)

        # Test update existing memory
        result2 = asyncio.run(remember.execute(
            key="user_name",
            content="The user's name is Anant Kumar",
            category="fact",
        ))
        ok("Remember updates existing key", "Remembered" in result2)

        # Verify only one memory exists for that key
        memories = store.list_memories()
        matching = [m for m in memories if m["key"] == "user_name"]
        ok("No duplicate memories for same key", len(matching) == 1)
        ok("Memory content updated", "Kumar" in matching[0]["content"])

        # Test without store
        remember_no_store = RememberTool()
        result = asyncio.run(remember_no_store.execute(key="test", content="test"))
        ok("Remember without store returns error", "not available" in result)

        recall_no_store = RecallTool()
        result = asyncio.run(recall_no_store.execute(query="test"))
        ok("Recall without store returns error", "not available" in result)

        store.close()


# ── Task 5: JSONL migration ──

def test_jsonl_migration():
    section("Task 5: JSONL to SQLite migration")
    from nanobot.session.manager import SessionManager
    from nanobot.session.store import ConversationStore

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()

        manager = SessionManager(workspace)
        manager.sessions_dir = Path(tmpdir) / "sessions"
        manager.sessions_dir.mkdir()

        # Create a JSONL session manually
        jsonl_path = manager.sessions_dir / "cli_test.jsonl"
        with open(jsonl_path, "w") as f:
            f.write(json.dumps({
                "_type": "metadata",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T01:00:00",
                "metadata": {},
            }) + "\n")
            f.write(json.dumps({"role": "user", "content": "Hello from JSONL", "timestamp": "2026-01-01T00:00:00"}) + "\n")
            f.write(json.dumps({"role": "assistant", "content": "Hi from JSONL", "timestamp": "2026-01-01T00:00:01"}) + "\n")

        # Set up SQLite store
        db_path = Path(tmpdir) / "test.db"
        manager._store = ConversationStore(db_path)
        manager._store.connect()

        # Run migration
        count = manager.migrate_jsonl_to_sqlite()
        ok("Migration imported messages", count == 2)

        # Verify data in SQLite
        history = manager._store.get_history("cli:test")
        ok("Migrated history has 2 messages", len(history) == 2)
        ok("Migrated content preserved", history[0]["content"] == "Hello from JSONL")

        # Search migrated data
        results = manager._store.search("JSONL")
        ok("Can search migrated data", len(results) > 0)

        manager._store.close()


# ── Integration: loop.py imports ──

def test_loop_imports():
    section("Integration: loop.py imports and tool registration")
    # Verify all new imports work
    from nanobot.agent.tools.plan import PlanTool
    from nanobot.agent.tools.memory_tools import RememberTool, RecallTool
    from nanobot.session.store import ConversationStore
    from nanobot.session.manager import Session, SessionManager

    ok("PlanTool importable", True)
    ok("RememberTool importable", True)
    ok("RecallTool importable", True)
    ok("ConversationStore importable", True)
    ok("Session has get_context_history", hasattr(Session, "get_context_history"))
    ok("Session has needs_summarization", hasattr(Session, "needs_summarization"))
    ok("SessionManager has get_store", hasattr(SessionManager, "get_store"))
    ok("SessionManager has migrate_jsonl_to_sqlite", hasattr(SessionManager, "migrate_jsonl_to_sqlite"))


# ── Run all tests ──

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PROJECT PLAN IMPLEMENTATION TESTS")
    print("=" * 60)

    test_gitignore()
    test_web_ui_markdown()
    test_strategy_skill()
    test_plan_tool()
    test_session_summarization()
    test_sqlite_store()
    test_session_manager_dual_write()
    test_memory_tools()
    test_jsonl_migration()
    test_loop_imports()

    print(f"\n{'='*60}")
    print(f"  RESULTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*60}")

    if FAIL > 0:
        exit(1)
    else:
        print("\n  All tests passed!")
        exit(0)
