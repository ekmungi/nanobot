"""MCP client manager -- connects to configured MCP servers and manages sessions."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


@dataclass
class MCPServerSpec:
    """Configuration for a single MCP server."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class MCPConnection:
    """An active connection to an MCP server."""
    spec: MCPServerSpec
    session: Any  # ClientSession
    tools: list[Any] = field(default_factory=list)  # List of MCP tool definitions
    _task: asyncio.Task | None = None  # The background task owning this connection
    _ready: asyncio.Event = field(default_factory=asyncio.Event)
    _stop: asyncio.Event = field(default_factory=asyncio.Event)
    _error: str | None = None


class MCPClientManager:
    """
    Manages connections to multiple MCP servers.

    Each server connection runs in its own background task that owns the
    full async context manager lifecycle. This avoids anyio errors when
    shutting down from a different task.
    """

    def __init__(self, server_specs: list[MCPServerSpec] | None = None):
        self._specs = server_specs or []
        self._connections: dict[str, MCPConnection] = {}
        self._started = False

    @property
    def is_available(self) -> bool:
        return MCP_AVAILABLE

    async def start(self) -> None:
        """Connect to all enabled MCP servers and discover their tools."""
        if not MCP_AVAILABLE:
            logger.warning("MCP SDK not installed (pip install mcp). MCP tools disabled.")
            return

        if not self._specs:
            return

        # Launch each server in its own background task
        for spec in self._specs:
            if not spec.enabled:
                continue
            conn = MCPConnection(spec=spec, session=None)
            conn._task = asyncio.create_task(
                self._run_server(conn),
                name=f"mcp-{spec.name}",
            )
            self._connections[spec.name] = conn

        # Wait for all connections to be ready (or fail)
        if self._connections:
            await asyncio.gather(
                *(conn._ready.wait() for conn in self._connections.values()),
                return_exceptions=True,
            )

        # Remove failed connections
        failed = [name for name, conn in self._connections.items() if conn._error]
        for name in failed:
            conn = self._connections.pop(name)
            if conn._task and not conn._task.done():
                conn._task.cancel()
            logger.error(f"MCP server '{name}' failed: {conn._error}")

        self._started = True
        total_tools = sum(len(c.tools) for c in self._connections.values())
        if self._connections:
            logger.info(
                f"MCP: connected to {len(self._connections)} server(s), "
                f"{total_tools} tool(s) available"
            )

    async def stop(self) -> None:
        """Signal all server tasks to shut down and wait for them."""
        for name, conn in self._connections.items():
            conn._stop.set()  # Signal the task to exit

        # Wait for all tasks to finish (they close their own context managers)
        tasks = [
            conn._task for conn in self._connections.values()
            if conn._task and not conn._task.done()
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._connections.clear()
        self._started = False
        logger.info("MCP: all servers disconnected")

    async def _run_server(self, conn: MCPConnection) -> None:
        """
        Background task that owns the full lifecycle of one MCP server connection.

        The context managers are entered and exited within the SAME task,
        which is what anyio requires.
        """
        spec = conn.spec
        try:
            # Build environment
            env = dict(os.environ)
            env.update(spec.env)

            server_params = StdioServerParameters(
                command=spec.command,
                args=spec.args,
                env=env,
            )

            # Open stdio transport -- context manager stays open for the task's lifetime
            async with stdio_client(server_params) as (read_stream, write_stream):
                # Open the session
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    # Discover tools
                    tools_result = await session.list_tools()
                    conn.session = session
                    conn.tools = tools_result.tools if tools_result else []

                    tool_names = [t.name for t in conn.tools]
                    logger.info(f"MCP server '{spec.name}': {len(conn.tools)} tools - {tool_names}")

                    # Signal that we're ready
                    conn._ready.set()

                    # Stay alive until told to stop
                    await conn._stop.wait()

                    logger.debug(f"MCP server '{spec.name}': shutting down")

            # Context managers exit cleanly here, in the same task

        except Exception as e:
            conn._error = str(e)
            conn._ready.set()  # Unblock the waiter even on failure
            logger.error(f"MCP server '{spec.name}' error: {e}")

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> str:
        """
        Execute a tool call on a specific MCP server.

        Returns the text result.
        """
        conn = self._connections.get(server_name)
        if not conn:
            return f"Error: MCP server '{server_name}' not connected"

        if not conn.session:
            return f"Error: MCP server '{server_name}' session not ready"

        try:
            result = await conn.session.call_tool(tool_name, arguments=arguments)
            # Extract text content from result
            parts = []
            for content_block in result.content:
                if hasattr(content_block, "text"):
                    parts.append(content_block.text)
                elif hasattr(content_block, "data"):
                    parts.append(f"[binary data: {len(content_block.data)} bytes]")
                else:
                    parts.append(str(content_block))
            return "\n".join(parts) if parts else "Tool executed successfully (no output)"
        except Exception as e:
            logger.error(f"MCP tool call failed ({server_name}/{tool_name}): {e}")
            return f"Error calling tool: {e}"

    def get_all_tools(self) -> list[tuple[str, Any]]:
        """
        Get all tools from all connected servers.

        Returns list of (server_name, mcp_tool) tuples.
        """
        result = []
        for name, conn in self._connections.items():
            for tool in conn.tools:
                result.append((name, tool))
        return result
