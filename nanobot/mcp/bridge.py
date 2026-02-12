"""Bridge MCP tools into nanobot's Tool registry."""

from __future__ import annotations

from typing import Any

from loguru import logger
from nanobot.agent.tools.base import Tool
from nanobot.mcp.client import MCPClientManager


def _simplify_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Simplify an MCP tool's JSON Schema to reduce token usage.

    Many MCP servers (especially Notion) embed massive $defs / definitions
    blocks that repeat across every tool, ballooning the tool list to tens of
    thousands of tokens.  Most LLMs don't need (or benefit from) deeply
    nested JSON Schema references — they work better with a flat parameter
    list showing name, type, and description.

    This function:
    1. Resolves top-level $ref pointers (one level)
    2. Strips $defs / definitions blocks
    3. Keeps only the essential fields an LLM needs to generate a call
    """
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}

    schema = dict(schema)  # shallow copy
    defs = schema.pop("$defs", schema.pop("definitions", {}))

    # If the top-level is a $ref, resolve it
    if "$ref" in schema and defs:
        ref_path = schema["$ref"].rsplit("/", 1)[-1]
        if ref_path in defs:
            schema = dict(defs[ref_path])
            defs = {}  # already resolved

    # Strip $defs from nested properties too (some servers put them everywhere)
    properties = schema.get("properties", {})
    clean_props = {}
    for prop_name, prop_schema in properties.items():
        if isinstance(prop_schema, dict):
            prop_copy = {k: v for k, v in prop_schema.items()
                         if k not in ("$defs", "definitions")}
            # Resolve simple $ref in properties
            if "$ref" in prop_copy and defs:
                ref_path = prop_copy["$ref"].rsplit("/", 1)[-1]
                if ref_path in defs:
                    resolved = dict(defs[ref_path])
                    # Keep description from original if resolved doesn't have one
                    if "description" in prop_copy and "description" not in resolved:
                        resolved["description"] = prop_copy["description"]
                    prop_copy = resolved
            # Remove any remaining nested $defs
            prop_copy.pop("$defs", None)
            prop_copy.pop("definitions", None)
            clean_props[prop_name] = prop_copy
        else:
            clean_props[prop_name] = prop_schema

    result = {"type": "object", "properties": clean_props}
    if "required" in schema:
        result["required"] = schema["required"]
    if "additionalProperties" in schema:
        result["additionalProperties"] = schema["additionalProperties"]
    return result


class MCPBridgeTool(Tool):
    """
    Wraps a single MCP server tool as a nanobot Tool.

    This allows the agent loop to treat MCP tools identically to built-in tools.
    The tool name is prefixed with the server name to avoid collisions:
      e.g., "notion__API-post-search", "filesystem__read_file"
    """

    def __init__(self, server_name: str, mcp_tool: Any, manager: MCPClientManager):
        self._server_name = server_name
        self._mcp_tool = mcp_tool
        self._manager = manager
        # Pre-compute simplified schema once
        raw_schema = mcp_tool.inputSchema
        if raw_schema:
            src = dict(raw_schema) if not isinstance(raw_schema, dict) else raw_schema
            self._simplified_params = _simplify_schema(src)
        else:
            self._simplified_params = {"type": "object", "properties": {}}

    @property
    def name(self) -> str:
        return f"{self._server_name}__{self._mcp_tool.name}"

    @property
    def description(self) -> str:
        return self._mcp_tool.description or f"MCP tool from {self._server_name}"

    @property
    def parameters(self) -> dict[str, Any]:
        return self._simplified_params

    async def execute(self, **kwargs: Any) -> str:
        return await self._manager.call_tool(
            self._server_name,
            self._mcp_tool.name,
            kwargs,
        )


def register_mcp_tools(manager: MCPClientManager, registry: "ToolRegistry") -> int:
    """
    Register all MCP tools from connected servers into the nanobot tool registry.

    Returns the number of tools registered.
    """
    count = 0
    for server_name, mcp_tool in manager.get_all_tools():
        bridge_tool = MCPBridgeTool(server_name, mcp_tool, manager)
        registry.register(bridge_tool)
        count += 1

    if count:
        _log_schema_size(manager, registry)

    return count


def register_mcp_tools_for_server(
    server_name: str, manager: MCPClientManager, registry: "ToolRegistry"
) -> int:
    """
    Register MCP bridge tools for a single server.

    Used when semantic wrappers are not available for a server, so we fall back
    to exposing the raw MCP tool names to the LLM.

    Returns the number of tools registered.
    """
    count = 0
    for name, mcp_tool in manager.get_all_tools():
        if name != server_name:
            continue
        bridge_tool = MCPBridgeTool(server_name, mcp_tool, manager)
        registry.register(bridge_tool)
        count += 1
    return count


def _log_schema_size(manager: MCPClientManager, registry: "ToolRegistry") -> None:
    """Log total schema size for debugging token usage."""
    import json
    total = sum(
        len(json.dumps({"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}))
        for t in [registry.get(n) for n in [f"{s}__{t.name}" for s, t in manager.get_all_tools()]]
        if t is not None
    )
    if total:
        logger.info(f"MCP bridge tools schema size: {total:,} chars (~{total // 4:,} tokens)")
