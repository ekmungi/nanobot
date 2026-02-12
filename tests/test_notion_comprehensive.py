"""
Comprehensive tests for Notion MCP wrapper tools.

Run with:
    cd C:/Users/ekmun/Dev/nanobot
    uv run python tests/test_notion_comprehensive.py

Tests verify:
- Property formatting to markdown
- Rich text conversion
- NotionResponse object
- Tool basic functionality
- Error handling
"""

import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import tools
try:
    from nanobot.mcp.wrappers.notion import (
        NotionSearchTool,
        NotionReadPageTool,
        NotionQueryDatabaseTool,
        NotionCreatePageTool,
        NotionUpdatePageTool,
        _format_property_for_markdown,
        _format_rich_text,
        _extract_property_value,
        NotionResponse,
    )
    print("[OK] All imports successful")
except ImportError as e:
    print(f"[FAIL] Import failed: {e}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test Utilities
# ---------------------------------------------------------------------------

class MockManager:
    """Mock MCP manager for testing."""

    def __init__(self, is_remote=True):
        self.is_remote = is_remote
        self.call_results = {}

    def get_all_tools(self):
        """Return mock tool list."""
        if self.is_remote:
            return [
                ("notion", type("Tool", (), {"name": "notion-fetch"})()),
                ("notion", type("Tool", (), {"name": "notion-search"})()),
            ]
        else:
            return [
                ("notion", type("Tool", (), {"name": "API-post-search"})()),
                ("notion", type("Tool", (), {"name": "API-retrieve-a-page"})()),
            ]

    async def call_tool(self, server, tool_name, args):
        """Return mock response."""
        key = (server, tool_name)
        if key in self.call_results:
            return self.call_results[key]
        return json.dumps({"error": "Not configured"})


# ---------------------------------------------------------------------------
# Test: Property Formatting
# ---------------------------------------------------------------------------

def test_format_property_select():
    """Format select property."""
    prop = {"type": "select", "select": {"name": "Done"}}
    result = _format_property_for_markdown("Status", prop)
    assert "`Done`" in result, f"Expected '`Done`' in '{result}'"
    print("[PASS] test_format_property_select")


def test_format_property_date():
    """Format date property."""
    prop = {"type": "date", "date": {"start": "2025-02-15", "end": None}}
    result = _format_property_for_markdown("Due", prop)
    assert "2025-02-15" in result, f"Expected date in '{result}'"
    print("[PASS] test_format_property_date")


def test_format_property_checkbox_true():
    """Format checked checkbox."""
    prop = {"type": "checkbox", "checkbox": True}
    result = _format_property_for_markdown("Done", prop)
    assert "Done" in result, f"Expected 'Done' in '{result}'"
    print("[PASS] test_format_property_checkbox_true")


def test_format_property_checkbox_false():
    """Format unchecked checkbox."""
    prop = {"type": "checkbox", "checkbox": False}
    result = _format_property_for_markdown("Done", prop)
    assert "☐" in result, f"Expected unchecked in '{result}'"
    print("[PASS] test_format_property_checkbox_false")


def test_format_property_people():
    """Format people property."""
    prop = {
        "type": "people",
        "people": [{"name": "Alice"}, {"name": "Bob"}],
    }
    result = _format_property_for_markdown("Assigned", prop)
    assert "@Alice" in result, f"Expected '@Alice' in '{result}'"
    assert "@Bob" in result, f"Expected '@Bob' in '{result}'"
    print("[PASS] test_format_property_people")


def test_format_property_relation():
    """Format relation property."""
    prop = {"type": "relation", "relation": [{"id": "a"}, {"id": "b"}]}
    result = _format_property_for_markdown("Related", prop)
    assert "2" in result, f"Expected '2' in '{result}'"
    print("[PASS] test_format_property_relation")


# ---------------------------------------------------------------------------
# Test: Rich Text Formatting
# ---------------------------------------------------------------------------

def test_format_rich_text_bold():
    """Format bold text."""
    rich_text = [
        {"plain_text": "bold text", "annotations": {"bold": True}}
    ]
    result = _format_rich_text(rich_text)
    assert "**bold text**" in result, f"Expected bold in '{result}'"
    print("[PASS] test_format_rich_text_bold")


def test_format_rich_text_italic():
    """Format italic text."""
    rich_text = [
        {"plain_text": "italic text", "annotations": {"italic": True}}
    ]
    result = _format_rich_text(rich_text)
    assert "*italic text*" in result, f"Expected italic in '{result}'"
    print("[PASS] test_format_rich_text_italic")


def test_format_rich_text_code():
    """Format code text."""
    rich_text = [
        {"plain_text": "function()", "annotations": {"code": True}}
    ]
    result = _format_rich_text(rich_text)
    assert "`function()`" in result, f"Expected code in '{result}'"
    print("[PASS] test_format_rich_text_code")


def test_format_rich_text_link():
    """Format link."""
    rich_text = [
        {
            "plain_text": "click here",
            "href": "https://example.com",
            "annotations": {},
        }
    ]
    result = _format_rich_text(rich_text)
    assert "[click here](https://example.com)" in result, f"Expected link in '{result}'"
    print("[PASS] test_format_rich_text_link")


# ---------------------------------------------------------------------------
# Test: NotionResponse Object
# ---------------------------------------------------------------------------

def test_response_basic():
    """Create basic response."""
    resp = NotionResponse(markdown="# Test\nContent here")
    assert resp.markdown == "# Test\nContent here"
    assert resp.success is True
    print("[PASS] test_response_basic")


def test_response_with_completeness():
    """Response with completeness info."""
    breakdown = {"blocks": {"count": 5, "total": 5}}
    resp = NotionResponse(
        markdown="Content",
        completeness_percentage=100,
        completeness_breakdown=breakdown,
    )
    assert resp.completeness["percentage"] == 100
    assert "blocks" in resp.completeness["breakdown"]
    print("[PASS] test_response_with_completeness")


def test_response_with_context_warning():
    """Response with context warning."""
    resp = NotionResponse(
        markdown="x" * 10000,
        context_warning="This is large. Consider spawning subagents.",
    )
    assert resp.context_warning is not None
    print("[PASS] test_response_with_context_warning")


def test_response_to_string():
    """Convert response to string (metadata in object, not in output)."""
    resp = NotionResponse(
        markdown="# Test",
        completeness_percentage=95,
        completeness_breakdown={"items": {"count": 10, "total": 10}},
        log="Fetched 10 items",
    )
    result = resp.to_string()

    # String output should contain ONLY markdown (no metadata footer)
    assert "# Test" in result, f"Expected markdown in '{result}'"
    assert isinstance(result, str)
    assert len(result) > 0

    # Metadata should NOT be in string output (to avoid cluttering user-facing response)
    assert "Data Completeness" not in result, f"Metadata footer should not appear in string output"
    assert "Extraction Log" not in result, f"Log should not appear in string output"

    # But metadata SHOULD be accessible via object attributes
    assert resp.completeness["percentage"] == 95, "Completeness should be in object"
    assert "items" in resp.completeness["breakdown"], "Breakdown should be in object"
    assert resp.log == "Fetched 10 items", "Log should be in object"

    print("[PASS] test_response_to_string")


# ---------------------------------------------------------------------------
# Test: Tool Basic Functionality
# ---------------------------------------------------------------------------

async def test_search_tool_initialization():
    """Initialize search tool."""
    manager = MockManager(is_remote=True)
    tool = NotionSearchTool(manager, is_remote=True)
    assert tool.name == "notion_search"
    assert "search" in tool.description.lower()
    print("[PASS] test_search_tool_initialization")


async def test_read_page_tool_initialization():
    """Initialize read page tool."""
    manager = MockManager(is_remote=True)
    tool = NotionReadPageTool(manager, is_remote=True)
    assert tool.name == "notion_read_page"
    assert "read" in tool.description.lower()
    print("[PASS] test_read_page_tool_initialization")


async def test_query_database_tool_initialization():
    """Initialize query database tool."""
    manager = MockManager(is_remote=True)
    tool = NotionQueryDatabaseTool(manager, is_remote=True)
    assert tool.name == "notion_query_database"
    print("[PASS] test_query_database_tool_initialization")


# ---------------------------------------------------------------------------
# Test: Error Handling
# ---------------------------------------------------------------------------

def test_extract_property_value_select():
    """Extract select property value."""
    prop = {"type": "select", "select": {"name": "Done"}}
    result = _extract_property_value(prop)
    assert "Done" in result
    print("[PASS] test_extract_property_value_select")


def test_extract_property_value_date():
    """Extract date property value."""
    prop = {"type": "date", "date": {"start": "2025-02-15", "end": None}}
    result = _extract_property_value(prop)
    assert "2025-02-15" in result
    print("[PASS] test_extract_property_value_date")


def test_extract_property_value_checkbox():
    """Extract checkbox property value."""
    prop = {"type": "checkbox", "checkbox": True}
    result = _extract_property_value(prop)
    assert result in ("Yes", "True", "true")
    print("[PASS] test_extract_property_value_checkbox")


# ---------------------------------------------------------------------------
# Test: Truncation Fixes
# ---------------------------------------------------------------------------

def test_no_silent_truncation():
    """Verify that markdown content is NOT silently truncated."""
    # Create a response with 10KB of content
    large_content = "# Large Page\n\n" + ("Content line\n" * 500)  # ~7KB
    resp = NotionResponse(
        markdown=large_content,
        completeness_percentage=95,
        context_warning="This is large. Consider spawning subagents.",
    )

    result = resp.to_string()

    # Verify complete content is in the output (not truncated)
    assert len(result) > 5000, f"Expected >5000 chars, got {len(result)}"
    assert "Content line" in result, "Expected content should be present"
    assert "truncated" not in result.lower(), "Should not show 'truncated' message"
    print("[PASS] test_no_silent_truncation")


def test_context_warning_small_page():
    """Verify no warning for small pages."""
    from nanobot.mcp.wrappers.notion import _generate_context_warning

    # Small content (5KB)
    small_content = "x" * 5000
    warning = _generate_context_warning(len(small_content))
    assert warning is None, f"Expected no warning for 5KB, got: {warning}"
    print("[PASS] test_context_warning_small_page")


def test_context_warning_medium_page():
    """Verify tiered warning for medium pages (8-20KB)."""
    from nanobot.mcp.wrappers.notion import _generate_context_warning

    # Medium content (10KB)
    medium_content = "x" * 10000
    warning = _generate_context_warning(len(medium_content))
    assert warning is not None, "Expected warning for 10KB"
    assert "Consider spawning" in warning, f"Expected 'Consider spawning', got: {warning}"
    print("[PASS] test_context_warning_medium_page")


def test_context_warning_large_page():
    """Verify tiered warning for large pages (20-50KB)."""
    from nanobot.mcp.wrappers.notion import _generate_context_warning

    # Large content (25KB)
    large_content = "x" * 25000
    warning = _generate_context_warning(len(large_content))
    assert warning is not None, "Expected warning for 25KB"
    assert "RECOMMENDED" in warning, f"Expected 'RECOMMENDED', got: {warning}"
    print("[PASS] test_context_warning_large_page")


def test_context_warning_huge_page():
    """Verify tiered warning for huge pages (>50KB)."""
    from nanobot.mcp.wrappers.notion import _generate_context_warning

    # Huge content (60KB)
    huge_content = "x" * 60000
    warning = _generate_context_warning(len(huge_content))
    assert warning is not None, "Expected warning for 60KB"
    assert "STRONGLY RECOMMENDED" in warning, f"Expected 'STRONGLY RECOMMENDED', got: {warning}"
    print("[PASS] test_context_warning_huge_page")


def test_meeting_transcript_complete():
    """Test real-world case: meeting with transcript should be returned complete."""
    # Simulate a meeting page with title + summary + transcript
    meeting_content = """# Meeting 2026-02-11

## Attendees
- Alice
- Bob

## AI Summary
Key discussion points about the SmartCholangio validation study.
Discussed sensitivity (84.1%), specificity (87.9%), and accuracy (86.0%).
Identified need for per-device performance breakdown and confidence threshold handling.

## Transcript

Alice: Let's review the SmartCholangio validation study results.
Bob: The overall accuracy is 86%, which is solid.
Alice: But we need to analyze frame-level performance separately.
Bob: Yes, the frame accuracy of 76.4% with 27.1% SD shows significant instability.
Alice: What about per-device breakdown? We have SpyGlass DS2, SpyGlass DS, and EyeMax.
Bob: That's missing from the current report. We need device-specific performance metrics.
Alice: Agreed. Also need confidence threshold analysis - mean is 78.8% but no breakdown by level.
Bob: Right, and the multi-frame decision logic needs documentation. Currently just >50% majority vote.
Alice: Let's add all of this to our next report. This is critical for clinical readiness.
Bob: Definitely. Without these details, we can't assess real-world deployment viability."""

    resp = NotionResponse(
        markdown=meeting_content,
        completeness_percentage=95,
        context_warning="This page contains a full meeting transcript. Consider spawning subagents to analyze different sections.",
    )

    result = resp.to_string()

    # Verify complete transcript is present
    assert "Transcript" in result, "Should include Transcript section"
    assert "frame-level performance" in result, "Should include technical details"
    assert "confidence threshold" in result, "Should include confidence discussion"
    assert len(result) > 1000, f"Should be >1000 chars, got {len(result)}"
    assert "truncated" not in result.lower(), "Should not be truncated"
    assert "[WARNING]" in result, "Should have context warning for large content"
    print("[PASS] test_meeting_transcript_complete")


def test_ai_transcript_extraction_completeness():
    """Verify AI transcript and summary extraction statistics are accurate."""
    from nanobot.mcp.wrappers.notion import _extract_ai_section_info

    # Test content with AI summary and transcript
    test_content = """# Weekly Product Sync

## AI Summary
This week focused on improving the API response times and user experience.
Key metrics: 23% reduction in latency, 15% improvement in user satisfaction scores.

## Transcript

Alice: Let's start with this week's progress update.
Bob: We achieved 23% latency reduction on the core API endpoints.
Carol: And user satisfaction went up 15% based on our latest survey.
Alice: That's great! What are the next priorities?
Bob: We need to focus on database query optimization.
Carol: Also need to improve error handling for edge cases.
Alice: Let's schedule those for next sprint.
Bob: Agreed, I'll create the tickets today.
Carol: Perfect, looking forward to the improvements."""

    # Extract AI section info
    info = _extract_ai_section_info(test_content)

    # Verify summary was extracted
    assert info.get("summary_chars", 0) > 0, "Should extract summary character count"
    assert info.get("summary_words", 0) > 0, "Should extract summary word count"
    summary_chars = info["summary_chars"]
    assert summary_chars > 50, f"Summary should be >50 chars, got {summary_chars}"
    print(f"  Summary: {summary_chars} chars, {info['summary_words']} words")

    # Verify transcript was extracted
    assert info.get("transcript_chars", 0) > 0, "Should extract transcript character count"
    assert info.get("transcript_words", 0) > 0, "Should extract transcript word count"
    assert info.get("speaker_lines", 0) > 0, "Should extract speaker line count"
    transcript_chars = info["transcript_chars"]
    speaker_count = info["speaker_lines"]
    assert transcript_chars > 200, f"Transcript should be >200 chars, got {transcript_chars}"
    assert speaker_count > 3, f"Should have >3 speakers, got {speaker_count}"
    print(f"  Transcript: {transcript_chars} chars, {info['transcript_words']} words, {speaker_count} speaker lines")

    # Verify NotionResponse includes these stats
    resp = NotionResponse(
        markdown=test_content,
        completeness_percentage=95,
        completeness_breakdown={
            "ai_section_sizes": {
                "summary_chars": info.get("summary_chars", 0),
                "transcript_chars": info.get("transcript_chars", 0),
                "transcript_speaker_lines": info.get("speaker_lines", 0),
            }
        },
        log=f"Test log with AI stats: summary {info.get('summary_chars', 0)} chars, transcript {info.get('transcript_chars', 0)} chars"
    )

    assert resp.completeness["breakdown"]["ai_section_sizes"]["summary_chars"] > 0
    assert resp.completeness["breakdown"]["ai_section_sizes"]["transcript_chars"] > 0
    assert "AI stats" in resp.log
    print("[PASS] test_ai_transcript_extraction_completeness")


# ---------------------------------------------------------------------------
# Main Test Runner
# ---------------------------------------------------------------------------

async def async_tests():
    """Run async tests."""
    await test_search_tool_initialization()
    await test_read_page_tool_initialization()
    await test_query_database_tool_initialization()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("NOTION WRAPPER COMPREHENSIVE TESTS")
    print("=" * 60 + "\n")

    # Property formatting tests
    print("Property Formatting Tests:")
    test_format_property_select()
    test_format_property_date()
    test_format_property_checkbox_true()
    test_format_property_checkbox_false()
    test_format_property_people()
    test_format_property_relation()

    # Rich text formatting tests
    print("\nRich Text Formatting Tests:")
    test_format_rich_text_bold()
    test_format_rich_text_italic()
    test_format_rich_text_code()
    test_format_rich_text_link()

    # NotionResponse tests
    print("\nNotionResponse Object Tests:")
    test_response_basic()
    test_response_with_completeness()
    test_response_with_context_warning()
    test_response_to_string()

    # Tool initialization tests
    print("\nTool Initialization Tests:")
    asyncio.run(async_tests())

    # Property extraction tests
    print("\nProperty Extraction Tests:")
    test_extract_property_value_select()
    test_extract_property_value_date()
    test_extract_property_value_checkbox()

    # Truncation fix tests
    print("\nTruncation and Context Warning Tests:")
    test_no_silent_truncation()
    test_context_warning_small_page()
    test_context_warning_medium_page()
    test_context_warning_large_page()
    test_context_warning_huge_page()
    test_meeting_transcript_complete()

    # AI transcript extraction tests
    print("\nAI Content Extraction Tests:")
    test_ai_transcript_extraction_completeness()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED [PASS]")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
