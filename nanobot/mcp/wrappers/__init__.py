"""Semantic wrapper tools for MCP servers.

Instead of exposing raw MCP tool names (e.g. "notion__API-post-search") to the LLM,
wrappers provide simple, intuitive tool names (e.g. "notion_search") that internally
route to the correct MCP calls deterministically.

This eliminates tool-name hallucination from small/free models entirely — the LLM
never sees the raw MCP tool names.
"""

from __future__ import annotations

import importlib
from typing import Any, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.agent.tools.base import Tool
    from nanobot.mcp.client import MCPClientManager

# Maps MCP server names to their wrapper modules.
# Each module must expose: get_tools(manager: MCPClientManager) -> list[Tool]
_REGISTRY: dict[str, str] = {
    "notion": "nanobot.mcp.wrappers.notion",
}


def has_wrappers(server_name: str) -> bool:
    """Check if semantic wrappers exist for a given MCP server name."""
    return server_name in _REGISTRY


def get_wrappers(server_name: str, manager: "MCPClientManager") -> list["Tool"]:
    """
    Return semantic wrapper tools for a known MCP server.

    Args:
        server_name: The MCP server name (e.g. "notion").
        manager: The MCP client manager for making raw tool calls.

    Returns:
        List of Tool instances, or empty list if no wrappers exist.
    """
    module_path = _REGISTRY.get(server_name)
    if not module_path:
        return []

    try:
        module = importlib.import_module(module_path)
        tools = module.get_tools(manager)
        logger.info(
            f"Loaded {len(tools)} semantic wrapper(s) for '{server_name}': "
            f"{[t.name for t in tools]}"
        )
        return tools
    except Exception as e:
        logger.error(f"Failed to load wrappers for '{server_name}': {e}")
        return []
