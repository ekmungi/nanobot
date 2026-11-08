"""Tool registry for dynamic tool management."""

from typing import Any

from loguru import logger
from nanobot.agent.tools.base import Tool

# URL patterns that should be intercepted and routed to semantic wrappers
# instead of being fetched by web_fetch. Maps domain pattern → (target_tool, param_transform).
_URL_INTERCEPTS: dict[str, tuple[str, str]] = {
    "notion.so": ("notion_read_page", "page_id"),
    "notion.site": ("notion_read_page", "page_id"),
}


class ToolRegistry:
    """
    Registry for agent tools.

    Allows dynamic registration and execution of tools.
    Includes fuzzy matching to recover from LLM tool name hallucinations.
    Includes URL interception to route Notion URLs away from web_fetch.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format."""
        return [tool.to_schema() for tool in self._tools.values()]

    def _find_closest_tool(self, name: str) -> Tool | None:
        """
        Try to find the tool the LLM probably meant.

        Handles common LLM mistakes like:
        - Wrong separator: "notion_search" → "notion__API-post-search"
        - Missing prefix: "API-post-search" → "notion__API-post-search"
        - Underscore vs double-underscore: "notion_API-post-search" → "notion__API-post-search"
        """
        name_lower = name.lower().replace("-", "").replace("_", "")

        # Try exact match with normalized separators
        for tool_name, tool in self._tools.items():
            tool_lower = tool_name.lower().replace("-", "").replace("_", "")
            if name_lower == tool_lower:
                return tool

        # Try suffix match (LLM dropped the prefix)
        for tool_name, tool in self._tools.items():
            tool_lower = tool_name.lower().replace("-", "").replace("_", "")
            if tool_lower.endswith(name_lower) or name_lower.endswith(tool_lower):
                return tool

        # Try keyword match within the same server namespace
        # e.g., "notion_search" → find tools containing "notion" and "search"
        parts = [p for p in name.lower().replace("_", " ").replace("-", " ").split() if len(p) > 2]
        if parts:
            best_match = None
            best_score = 0
            for tool_name, tool in self._tools.items():
                tool_lower = tool_name.lower()
                score = sum(1 for p in parts if p in tool_lower)
                if score > best_score:
                    best_score = score
                    best_match = tool
            if best_score >= 2 or (best_score >= 1 and len(parts) == 1):
                return best_match

        return None

    def _suggest_tools(self, name: str) -> str:
        """Build a helpful error message with tool suggestions."""
        # Find which server the LLM was probably targeting
        prefix = name.split("_")[0].split("__")[0].lower() if "_" in name or "__" in name else ""

        matching_tools = []
        for tool_name in self._tools:
            if prefix and prefix in tool_name.lower():
                matching_tools.append(tool_name)

        if not matching_tools:
            # Show all tools grouped by prefix
            matching_tools = list(self._tools.keys())

        if len(matching_tools) > 10:
            matching_tools = matching_tools[:10] + [f"... and {len(matching_tools) - 10} more"]

        return ", ".join(matching_tools)

    def _check_url_intercept(self, name: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        """Check if a web_fetch call should be intercepted and routed elsewhere.

        When the LLM calls web_fetch on a Notion URL, we redirect to
        notion_read_page deterministically. This prevents the common failure
        where the LLM fetches notion.so (which requires JavaScript) and gets
        an empty page.

        Returns (new_tool_name, new_params) or None if no intercept needed.
        """
        if name != "web_fetch":
            return None

        url = params.get("url", "")
        if not url:
            return None

        for domain, (target_tool, param_name) in _URL_INTERCEPTS.items():
            if domain in url and target_tool in self._tools:
                logger.info(
                    f"[url-intercept] Redirecting web_fetch({url}) → {target_tool}"
                )
                return target_tool, {param_name: url}

        return None

    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """
        Execute a tool by name with given parameters.

        If the exact tool name isn't found, attempts fuzzy matching to recover
        from common LLM mistakes (wrong separators, missing prefixes, etc.).

        Also intercepts web_fetch calls for known domains (e.g. Notion) and
        routes them to the appropriate semantic wrapper tool instead.

        Args:
            name: Tool name.
            params: Tool parameters.

        Returns:
            Tool execution result as string.
        """
        # Check for URL intercepts (e.g., web_fetch on notion.so → notion_read_page)
        intercept = self._check_url_intercept(name, params)
        if intercept:
            name, params = intercept

        tool = self._tools.get(name)

        # Fuzzy match if exact name not found
        if not tool:
            fuzzy_match = self._find_closest_tool(name)
            if fuzzy_match:
                logger.warning(
                    f"Tool '{name}' not found, using closest match: '{fuzzy_match.name}'"
                )
                tool = fuzzy_match
            else:
                available = self._suggest_tools(name)
                return (
                    f"Error: Tool '{name}' not found. "
                    f"Available tools: {available}. "
                    f"Use the EXACT tool name from this list."
                )

        try:
            errors = tool.validate_params(params)
            if errors:
                return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors)
            return await tool.execute(**params)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"

    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
