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
        """Open the database connection and create tables."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                channel TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                summary TEXT,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls TEXT,
                token_estimate INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_messages_created
                ON messages(created_at);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated
                ON conversations(updated_at);

            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'fact',
                key TEXT,
                content TEXT NOT NULL,
                source_conversation TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                relevance_score REAL DEFAULT 1.0
            );

            CREATE INDEX IF NOT EXISTS idx_memory_category ON memory(category);
        """)

        # FTS tables need separate creation (can't use IF NOT EXISTS in all SQLite versions)
        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE messages_fts USING fts5(
                    content,
                    content=messages,
                    content_rowid=id
                )
            """)
            self._conn.execute("""
                CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
                    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                END
            """)
            self._conn.execute("""
                CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content)
                        VALUES('delete', old.id, old.content);
                END
            """)
            self._conn.execute("""
                CREATE TRIGGER messages_au AFTER UPDATE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content)
                        VALUES('delete', old.id, old.content);
                    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                END
            """)
        except sqlite3.OperationalError:
            pass  # Already exists

        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE memory_fts USING fts5(
                    key,
                    content,
                    content=memory,
                    content_rowid=id
                )
            """)
            self._conn.execute("""
                CREATE TRIGGER memory_ai AFTER INSERT ON memory BEGIN
                    INSERT INTO memory_fts(rowid, key, content)
                        VALUES (new.id, new.key, new.content);
                END
            """)
            self._conn.execute("""
                CREATE TRIGGER memory_ad AFTER DELETE ON memory BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, key, content)
                        VALUES('delete', old.id, old.key, old.content);
                END
            """)
            self._conn.execute("""
                CREATE TRIGGER memory_au AFTER UPDATE ON memory BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, key, content)
                        VALUES('delete', old.id, old.key, old.content);
                    INSERT INTO memory_fts(rowid, key, content)
                        VALUES (new.id, new.key, new.content);
                END
            """)
        except sqlite3.OperationalError:
            pass  # Already exists

        self._conn.commit()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token for English."""
        return len(text) // 4

    # ── Conversations ──

    def ensure_conversation(
        self, conversation_id: str, channel: str, chat_id: str
    ) -> None:
        """Create conversation record if it doesn't exist."""
        now = self._now_iso()
        self._conn.execute(
            """INSERT OR IGNORE INTO conversations
               (id, channel, chat_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (conversation_id, channel, chat_id, now, now),
        )
        self._conn.commit()

    def update_conversation_summary(
        self, conversation_id: str, summary: str
    ) -> None:
        """Update the rolling summary for a conversation."""
        now = self._now_iso()
        self._conn.execute(
            """UPDATE conversations
               SET summary = ?, updated_at = ?
               WHERE id = ?""",
            (summary, now, conversation_id),
        )
        self._conn.commit()

    def get_conversation_summary(self, conversation_id: str) -> str | None:
        """Get the summary for a conversation."""
        row = self._conn.execute(
            "SELECT summary FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        return row["summary"] if row else None

    def update_conversation_metadata(
        self, conversation_id: str, metadata: dict
    ) -> None:
        """Update metadata JSON blob for a conversation."""
        now = self._now_iso()
        self._conn.execute(
            """UPDATE conversations
               SET metadata = ?, updated_at = ?
               WHERE id = ?""",
            (json.dumps(metadata), now, conversation_id),
        )
        self._conn.commit()

    # ── Messages ──

    def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: list | None = None,
    ) -> int:
        """Save a message and return its ID."""
        now = self._now_iso()
        token_est = self._estimate_tokens(content)
        tc_json = json.dumps(tool_calls) if tool_calls else None

        cursor = self._conn.execute(
            """INSERT INTO messages
               (conversation_id, role, content, tool_calls, token_estimate, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (conversation_id, role, content, tc_json, token_est, now),
        )
        self._conn.commit()

        # Update conversation updated_at
        self._conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        self._conn.commit()

        return cursor.lastrowid

    def get_history(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get recent messages for a conversation."""
        rows = self._conn.execute(
            """SELECT role, content, tool_calls, token_estimate, created_at
               FROM messages
               WHERE conversation_id = ?
               ORDER BY id DESC
               LIMIT ?""",
            (conversation_id, limit),
        ).fetchall()

        messages = []
        for row in reversed(rows):  # Reverse to chronological order
            msg = {"role": row["role"], "content": row["content"]}
            if row["tool_calls"]:
                msg["tool_calls"] = json.loads(row["tool_calls"])
            messages.append(msg)
        return messages

    def get_message_count(self, conversation_id: str) -> int:
        """Get total message count for a conversation."""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_messages_for_summarization(
        self, conversation_id: str, offset: int, limit: int
    ) -> list[dict[str, Any]]:
        """Get a range of messages for summarization (oldest first)."""
        rows = self._conn.execute(
            """SELECT role, content FROM messages
               WHERE conversation_id = ?
               ORDER BY id ASC
               LIMIT ? OFFSET ?""",
            (conversation_id, limit, offset),
        ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    # ── Search ──

    def search(
        self,
        query: str,
        conversation_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Full-text search across conversations."""
        if conversation_id:
            rows = self._conn.execute(
                """SELECT m.id, m.role, m.content, m.created_at,
                          c.channel, c.chat_id, c.id as conversation_id
                   FROM messages_fts fts
                   JOIN messages m ON m.id = fts.rowid
                   JOIN conversations c ON c.id = m.conversation_id
                   WHERE messages_fts MATCH ?
                     AND m.conversation_id = ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, conversation_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT m.id, m.role, m.content, m.created_at,
                          c.channel, c.chat_id, c.id as conversation_id
                   FROM messages_fts fts
                   JOIN messages m ON m.id = fts.rowid
                   JOIN conversations c ON c.id = m.conversation_id
                   WHERE messages_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()

        return [dict(row) for row in rows]

    # ── Memory (cross-chat) ──

    def remember(
        self,
        key: str,
        content: str,
        category: str = "fact",
        source_conversation: str | None = None,
    ) -> int:
        """Store a memory entry. Updates existing entry if key matches."""
        now = self._now_iso()

        # Check for existing entry with same key
        existing = self._conn.execute(
            "SELECT id FROM memory WHERE key = ?", (key,)
        ).fetchone()

        if existing:
            self._conn.execute(
                """UPDATE memory
                   SET content = ?, category = ?, source_conversation = ?,
                       updated_at = ?, relevance_score = 1.0
                   WHERE id = ?""",
                (content, category, source_conversation, now, existing["id"]),
            )
            self._conn.commit()
            return existing["id"]

        cursor = self._conn.execute(
            """INSERT INTO memory
               (category, key, content, source_conversation, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (category, key, content, source_conversation, now, now),
        )
        self._conn.commit()
        return cursor.lastrowid

    def recall(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search persistent memory using FTS."""
        if category:
            rows = self._conn.execute(
                """SELECT m.id, m.category, m.key, m.content,
                          m.source_conversation, m.relevance_score,
                          m.created_at, m.updated_at
                   FROM memory_fts fts
                   JOIN memory m ON m.id = fts.rowid
                   WHERE memory_fts MATCH ?
                     AND m.category = ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, category, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT m.id, m.category, m.key, m.content,
                          m.source_conversation, m.relevance_score,
                          m.created_at, m.updated_at
                   FROM memory_fts fts
                   JOIN memory m ON m.id = fts.rowid
                   WHERE memory_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()

        return [dict(row) for row in rows]

    def list_memories(
        self, category: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List all memory entries, optionally filtered by category."""
        if category:
            rows = self._conn.execute(
                """SELECT id, category, key, content, relevance_score,
                          created_at, updated_at
                   FROM memory
                   WHERE category = ?
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (category, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT id, category, key, content, relevance_score,
                          created_at, updated_at
                   FROM memory
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory entry by ID."""
        cursor = self._conn.execute(
            "DELETE FROM memory WHERE id = ?", (memory_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # ── Migration ──

    def import_jsonl_session(
        self,
        conversation_id: str,
        channel: str,
        chat_id: str,
        messages: list[dict],
        metadata: dict | None = None,
        created_at: str | None = None,
    ) -> int:
        """Import a JSONL session into SQLite. Returns number of messages imported."""
        now = self._now_iso()
        self.ensure_conversation(conversation_id, channel, chat_id)

        if created_at:
            self._conn.execute(
                "UPDATE conversations SET created_at = ? WHERE id = ?",
                (created_at, conversation_id),
            )

        if metadata:
            self.update_conversation_metadata(conversation_id, metadata)

        count = 0
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            ts = msg.get("timestamp", now)
            token_est = self._estimate_tokens(content)

            self._conn.execute(
                """INSERT INTO messages
                   (conversation_id, role, content, token_estimate, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (conversation_id, role, content, token_est, ts),
            )
            count += 1

        self._conn.commit()
        return count
