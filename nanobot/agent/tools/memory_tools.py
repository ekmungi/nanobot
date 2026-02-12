"""Cross-chat memory tools: remember and recall."""

from typing import Any

from nanobot.agent.tools.base import Tool


class RememberTool(Tool):
    """Store a fact or insight for future conversations."""

    name = "remember"
    description = (
        "Save important information for future reference across conversations. "
        "Use this to store facts, preferences, decisions, or context that should "
        "persist across chat sessions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["fact", "preference", "decision", "context"],
                "description": "Category of the memory",
            },
            "key": {
                "type": "string",
                "description": "Short topic label for easy lookup",
            },
            "content": {
                "type": "string",
                "description": "The information to remember",
            },
        },
        "required": ["key", "content"],
    }

    def __init__(self, store=None):
        self._store = store

    def set_store(self, store):
        """Set the conversation store (called during init)."""
        self._store = store

    async def execute(self, **kwargs: Any) -> str:
        if not self._store:
            return "Memory store not available."

        key = kwargs.get("key", "")
        content = kwargs.get("content", "")
        category = kwargs.get("category", "fact")

        try:
            self._store.remember(
                key=key,
                content=content,
                category=category,
            )
            return f"Remembered [{category}] {key}: {content[:100]}"
        except Exception as e:
            return f"Failed to save memory: {e}"


class RecallTool(Tool):
    """Search persistent memory and past conversations."""

    name = "recall"
    description = (
        "Search your memory and past conversations for relevant information. "
        "Use this when you need context from previous interactions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for",
            },
            "category": {
                "type": "string",
                "enum": ["fact", "preference", "decision", "context"],
                "description": "Optional: filter by category",
            },
        },
        "required": ["query"],
    }

    def __init__(self, store=None):
        self._store = store

    def set_store(self, store):
        """Set the conversation store (called during init)."""
        self._store = store

    async def execute(self, **kwargs: Any) -> str:
        if not self._store:
            return "Memory store not available."

        query = kwargs.get("query", "")
        category = kwargs.get("category")

        try:
            # Search persistent memory
            memories = self._store.recall(query, category=category, limit=5)

            # Also search past conversations
            conv_results = self._store.search(query, limit=5)

            lines = []

            if memories:
                lines.append("## Memories")
                for m in memories:
                    lines.append(
                        f"- [{m['category']}] **{m['key']}**: {m['content']}"
                    )

            if conv_results:
                lines.append("\n## Past Conversations")
                for r in conv_results:
                    preview = r["content"][:150]
                    lines.append(
                        f"- [{r['role']}] ({r['conversation_id']}): {preview}"
                    )

            if not lines:
                return f"No memories or past conversations found for: {query}"

            return "\n".join(lines)
        except Exception as e:
            return f"Failed to search memory: {e}"
