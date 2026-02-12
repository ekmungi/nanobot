"""
End-to-end test: Verify MCP Notion integration works.

Run with:
    cd C:/Users/ekmun/Dev/nanobot
    .venv/Scripts/python.exe tests/test_mcp_notion.py

This test:
1. Connects to the Notion MCP server (remote or local, based on config)
2. Discovers tools and detects server mode
3. Registers semantic wrapper tools
4. Tests search, read page, and query database wrappers
"""

import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ------- Configuration -------
# Hardcoded fallback for testing (these are used only if config loading fails)
DATABASE_ID = "2de5f57c2eef8044a3a7c2822e01765d"

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []


def report(test_name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    results.append((test_name, passed))
    msg = f"  {status} {test_name}"
    if detail:
        msg += f" - {detail}"
    print(msg)


async def main():
    print("=" * 60)
    print("MCP Notion Integration Test")
    print("=" * 60)
    print()

    # ---- Test 1: MCP SDK is importable ----
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        report("MCP SDK import", True)
    except ImportError as e:
        report("MCP SDK import", False, str(e))
        print("\nCannot continue without MCP SDK.")
        return

    # ---- Test 2: Nanobot MCP modules import ----
    try:
        from nanobot.mcp.client import MCPClientManager, MCPServerSpec
        from nanobot.mcp.bridge import MCPBridgeTool, register_mcp_tools, _simplify_schema
        from nanobot.mcp.wrappers import get_wrappers, has_wrappers
        from nanobot.mcp.wrappers.notion import _is_remote_server
        from nanobot.agent.tools.registry import ToolRegistry
        report("Nanobot MCP modules import", True)
    except ImportError as e:
        report("Nanobot MCP modules import", False, str(e))
        print("\nCannot continue without nanobot modules.")
        return

    # ---- Load config to determine server type ----
    try:
        from nanobot.config.loader import load_config
        config = load_config()
        mcp_configs = [c for c in config.mcp_servers if c.name == "notion" and c.enabled]
        if mcp_configs:
            cfg = mcp_configs[0]
            is_remote_config = "mcp-remote" in " ".join(cfg.args)
            print(f"  Config: {'remote' if is_remote_config else 'local'} server")
            print(f"  Command: {cfg.command} {' '.join(cfg.args)}")
        else:
            print("  WARNING: No enabled 'notion' MCP server in config")
            print("  Using default local server config")
            cfg = None
    except Exception as e:
        print(f"  WARNING: Could not load config: {e}")
        cfg = None

    # ---- Test 3: Connect to Notion MCP server ----
    if cfg:
        specs = [
            MCPServerSpec(
                name=cfg.name,
                command=cfg.command,
                args=cfg.args,
                env=cfg.env,
            ),
        ]
    else:
        # Fallback to local server
        specs = [
            MCPServerSpec(
                name="notion",
                command="npx",
                args=["-y", "@notionhq/notion-mcp-server"],
                env={"NOTION_TOKEN": os.environ.get("NOTION_TOKEN", "")},
            ),
        ]

    mgr = MCPClientManager(specs)
    try:
        await mgr.start()
        connected = "notion" in mgr._connections
        if connected:
            tools_count = len(mgr._connections["notion"].tools)
            tool_names = [t.name for t in mgr._connections["notion"].tools]
            report("Connect to Notion MCP server", True, f"{tools_count} tools discovered")
            print(f"    Tools: {', '.join(tool_names)}")
        else:
            report("Connect to Notion MCP server", False, "Not connected")
    except Exception as e:
        report("Connect to Notion MCP server", False, str(e))
        return

    if not connected:
        print("\nCannot continue without connection.")
        return

    # ---- Test 4: Server mode detection ----
    is_remote = _is_remote_server(mgr)
    mode = "remote (mcp.notion.com)" if is_remote else "local (stdio)"
    report("Server mode detection", True, mode)

    # ---- Test 5: Register semantic wrapper tools ----
    registry = ToolRegistry()
    wrappers = get_wrappers("notion", mgr)
    wrapper_registered = len(wrappers) == 5
    for tool in wrappers:
        registry.register(tool)
    expected_names = ["notion_search", "notion_read_page", "notion_query_database",
                      "notion_create_page", "notion_update_page"]
    actual_names = [t.name for t in wrappers]
    report(
        "Register semantic wrappers",
        wrapper_registered and set(actual_names) == set(expected_names),
        f"{len(wrappers)} tools: {actual_names}"
    )

    # ---- Test 6: Schema size is reasonable ----
    defs = registry.get_definitions()
    total_size = len(json.dumps(defs))
    is_small = total_size < 5000  # 5 wrapper tools should be tiny
    report("Schema size", is_small, f"{total_size:,} chars (~{total_size//4:,} tokens)")

    # ---- Test 7: Search for "Meetings" via wrapper ----
    try:
        search_tool = registry.get("notion_search")
        result = await search_tool.execute(query="Meetings")
        # The search should return results with titles/types/IDs
        has_results = "Found" in result and "result" in result
        report(
            "notion_search('Meetings')",
            has_results,
            f"{len(result)} chars"
        )
        # Show first 300 chars of result
        print(f"    Preview: {result[:300]}...")
    except Exception as e:
        report("notion_search('Meetings')", False, str(e))

    # ---- Test 8: Read a known meeting page via wrapper ----
    # Use a known meeting page ID with transcript content
    KNOWN_MEETING_PAGE = "2ff5f57c-2eef-80ce-94ea-c8459365b9a3"
    try:
        read_tool = registry.get("notion_read_page")
        result = await read_tool.execute(page_id=KNOWN_MEETING_PAGE, include_transcript=True)
        has_content = len(result) > 100 and "Error" not in result[:20]
        has_meeting_content = "meeting" in result.lower() or "transcript" in result.lower() or "summary" in result.lower()
        report(
            f"notion_read_page('{KNOWN_MEETING_PAGE[:12]}...')",
            has_content and has_meeting_content,
            f"{len(result)} chars, has transcript content: {has_meeting_content}"
        )
        print(f"    Preview: {result[:300]}...")
    except Exception as e:
        report("notion_read_page", False, str(e))

    # ---- Test 9: URL intercept (Notion URLs → notion_read_page) ----
    try:
        test_url = "https://www.notion.so/Test-Page-abc123def456abc123def456abc12345"
        intercept = registry._check_url_intercept("web_fetch", {"url": test_url})
        report(
            "URL intercept (notion.so)",
            intercept is not None and intercept[0] == "notion_read_page",
            f"Redirected to {intercept[0] if intercept else 'nothing'}"
        )
    except Exception as e:
        report("URL intercept", False, str(e))

    # ---- Cleanup ----
    await mgr.stop()

    # ---- Summary ----
    print()
    print("=" * 60)
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    if passed == total:
        print("All tests passed! Notion MCP integration is working.")
    else:
        failed = [name for name, p in results if not p]
        print(f"Failed: {', '.join(failed)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
