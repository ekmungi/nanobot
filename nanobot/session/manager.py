"""Session management for conversation history."""

import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable

from loguru import logger

from nanobot.utils.helpers import ensure_dir, safe_filename


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in JSONL format for easy reading and persistence.
    """

    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 chars per token for English."""
        return len(text) // 4

    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """
        Get message history for LLM context.

        Args:
            max_messages: Maximum messages to return.

        Returns:
            List of messages in LLM format.
        """
        # Get recent messages
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages

        # Convert to LLM format (just role and content)
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def get_context_history(
        self,
        max_tokens: int = 6000,
    ) -> list[dict[str, Any]]:
        """Get history with token budgeting and optional summary prefix.

        Returns recent messages that fit in max_tokens budget.
        If there are older messages and a stored summary exists,
        prepends the summary as a system message.
        """
        # Start from most recent, work backwards
        recent: list[dict[str, Any]] = []
        token_count = 0
        budget = int(max_tokens * 0.8)  # 80% for messages, rest for summary

        for msg in reversed(self.messages):
            msg_tokens = self._estimate_tokens(msg.get("content", ""))
            if token_count + msg_tokens > budget:
                break
            recent.insert(0, {"role": msg["role"], "content": msg["content"]})
            token_count += msg_tokens

        # If we have older messages, add summary prefix
        included_count = len(recent)
        total_count = len(self.messages)
        summary = self.metadata.get("summary")

        if included_count < total_count and summary:
            summary_msg = {
                "role": "system",
                "content": (
                    f"[Summary of earlier conversation "
                    f"({total_count - included_count} messages)]: {summary}"
                ),
            }
            recent.insert(0, summary_msg)

        return recent

    def needs_summarization(self) -> bool:
        """Check if the session needs summarization."""
        count = len(self.messages)
        has_summary = bool(self.metadata.get("summary"))
        # First summarization at 40 messages, re-summarize at 80
        if count > 40 and not has_summary:
            return True
        if count > 80 and has_summary:
            return True
        return False

    def get_messages_to_summarize(self) -> list[dict[str, Any]]:
        """Get older messages that should be summarized."""
        # Summarize the first half of messages
        half = len(self.messages) // 2
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.messages[:half]
        ]

    def set_summary(self, summary: str) -> None:
        """Store the conversation summary in metadata."""
        self.metadata["summary"] = summary

    def clear(self) -> None:
        """Clear all messages in the session."""
        self.messages = []
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions.

    Sessions are stored as JSONL files (primary) with dual-write to SQLite.
    SQLite provides full-text search and cross-chat memory capabilities.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(Path.home() / ".nanobot" / "sessions")
        self._cache: dict[str, Session] = {}
        self._store = None  # SQLite store (lazy init)

    def _get_store(self):
        """Lazy-initialize the SQLite store."""
        if self._store is None:
            try:
                from nanobot.session.store import ConversationStore
                db_path = Path.home() / ".nanobot" / "nanobot.db"
                self._store = ConversationStore(db_path)
                self._store.connect()
                logger.info(f"SQLite store connected: {db_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize SQLite store: {e}")
        return self._store

    def get_store(self):
        """Public accessor for the SQLite store (used by memory tools)."""
        return self._get_store()

    def _get_session_path(self, key: str) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def _parse_key(self, key: str) -> tuple[str, str]:
        """Parse a session key into (channel, chat_id)."""
        if ":" in key:
            parts = key.split(":", 1)
            return parts[0], parts[1]
        return "unknown", key

    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.

        Args:
            key: Session key (usually channel:chat_id).

        Returns:
            The session.
        """
        # Check cache
        if key in self._cache:
            return self._cache[key]

        # Try to load from disk
        session = self._load(key)
        if session is None:
            session = Session(key=key)

        self._cache[key] = session
        return session

    def _load(self, key: str) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None

            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata
            )
        except Exception as e:
            logger.warning(f"Failed to load session {key}: {e}")
            return None

    def save(self, session: Session) -> None:
        """Save a session to JSONL (primary) and SQLite (dual-write)."""
        # 1. Save to JSONL (primary storage)
        self._save_jsonl(session)

        # 2. Dual-write to SQLite
        self._save_sqlite(session)

        self._cache[session.key] = session

    def _save_jsonl(self, session: Session) -> None:
        """Save session to JSONL file."""
        path = self._get_session_path(session.key)

        with open(path, "w") as f:
            # Write metadata first
            metadata_line = {
                "_type": "metadata",
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata
            }
            f.write(json.dumps(metadata_line) + "\n")

            # Write messages
            for msg in session.messages:
                f.write(json.dumps(msg) + "\n")

    def _save_sqlite(self, session: Session) -> None:
        """Dual-write session data to SQLite."""
        store = self._get_store()
        if not store:
            return

        try:
            channel, chat_id = self._parse_key(session.key)
            store.ensure_conversation(session.key, channel, chat_id)

            # Get current count in SQLite
            existing_count = store.get_message_count(session.key)
            new_messages = session.messages[existing_count:]

            for msg in new_messages:
                store.save_message(
                    conversation_id=session.key,
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                )

            # Sync summary if it exists
            summary = session.metadata.get("summary")
            if summary:
                store.update_conversation_summary(session.key, summary)

        except Exception as e:
            logger.warning(f"SQLite dual-write failed for {session.key}: {e}")

    async def maybe_summarize(
        self,
        session: Session,
        summarizer: Callable[..., Awaitable[str]] | None = None,
    ) -> None:
        """Generate a summary for the session if needed.

        Args:
            session: The session to potentially summarize.
            summarizer: Async callable that takes a list of messages
                        and returns a summary string.
        """
        if not session.needs_summarization() or not summarizer:
            return

        messages_to_summarize = session.get_messages_to_summarize()
        if not messages_to_summarize:
            return

        try:
            summary = await summarizer(messages_to_summarize)
            session.set_summary(summary)
            self.save(session)
            logger.info(
                f"Generated summary for {session.key} "
                f"({len(messages_to_summarize)} messages)"
            )
        except Exception as e:
            logger.warning(f"Failed to summarize session {session.key}: {e}")

    def delete(self, key: str) -> bool:
        """
        Delete a session.

        Args:
            key: Session key.

        Returns:
            True if deleted, False if not found.
        """
        # Remove from cache
        self._cache.pop(key, None)

        # Remove file
        path = self._get_session_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.

        Returns:
            List of session info dicts.
        """
        sessions = []

        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                # Read just the metadata line
                with open(path) as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            sessions.append({
                                "key": path.stem.replace("_", ":"),
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                                "path": str(path)
                            })
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

    def migrate_jsonl_to_sqlite(self) -> int:
        """Import all existing JSONL sessions into SQLite. Returns count imported."""
        store = self._get_store()
        if not store:
            return 0

        imported = 0
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                key = path.stem.replace("_", ":", 1)
                session = self._load(key)
                if session and session.messages:
                    channel, chat_id = self._parse_key(key)
                    count = store.import_jsonl_session(
                        conversation_id=key,
                        channel=channel,
                        chat_id=chat_id,
                        messages=session.messages,
                        metadata=session.metadata,
                        created_at=session.created_at.isoformat(),
                    )
                    imported += count
            except Exception as e:
                logger.warning(f"Failed to migrate {path.name}: {e}")

        logger.info(f"Migrated {imported} messages to SQLite")
        return imported
