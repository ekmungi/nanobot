"""Semantic wrapper tools for the Notion MCP server.

Provides 5 intuitive tools that internally route to the correct raw Notion MCP
tool calls deterministically. Responses are compressed to concise markdown
suitable for small LLMs.

Supports BOTH the remote hosted MCP server (mcp.notion.com via mcp-remote)
and the local stdio server (@notionhq/notion-mcp-server).

Remote MCP tool mapping:
    notion_search         → notion-search
    notion_read_page      → notion-fetch
    notion_query_database → notion-fetch (for databases)
    notion_create_page    → notion-create-pages
    notion_update_page    → notion-update-page

Local MCP tool mapping (fallback):
    notion_search         → API-post-search
    notion_read_page      → API-retrieve-a-page + API-get-block-children
    notion_query_database → API-query-data-source
    notion_create_page    → API-post-page
    notion_update_page    → API-patch-page + API-patch-block-children
"""

from __future__ import annotations

import json
import re
from typing import Any, TYPE_CHECKING

from loguru import logger
from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.mcp.client import MCPClientManager

# Max characters returned to the LLM per tool call (~1,000 tokens)
MAX_RESPONSE_CHARS = 4000
SERVER_NAME = "notion"
CONTEXT_WARNING_THRESHOLD = 8000  # Trigger subagent suggestion at 8000 chars
CHUNK_SIZE_THRESHOLD = 15000  # Auto-chunk pages larger than this (for small LLMs)


# ---------------------------------------------------------------------------
# Enhanced Response Object
# ---------------------------------------------------------------------------

class NotionResponse:
    """Structured response from Notion tools with completeness info."""

    def __init__(
        self,
        markdown: str,
        success: bool = True,
        completeness_percentage: float = 100.0,
        completeness_breakdown: dict[str, Any] | None = None,
        context_warning: str | None = None,
        log: str = "",
    ):
        self.markdown = markdown
        self.success = success
        self.completeness = {
            "percentage": completeness_percentage,
            "breakdown": completeness_breakdown or {},
        }
        self.context_warning = context_warning
        self.log = log

    def to_string(self) -> str:
        """Format response for LLM as readable markdown (metadata available internally only).

        This method returns ONLY the markdown content plus context warning if present.
        Metadata (completeness, log) is kept in object attributes for LLM internal use
        but NOT included in the string output to avoid cluttering user-facing responses.

        The LLM can still access:
        - self.completeness: {percentage: X, breakdown: {...}}
        - self.log: extraction stats
        - self.context_warning: large response indicator
        """
        result = []

        # Only include context warning if present (helps LLM understand large responses)
        if self.context_warning:
            result.append(f"\n[WARNING] {self.context_warning}\n")

        result.append(self.markdown)

        # Metadata is intentionally NOT included in string output
        # It's available via: response.completeness, response.log, response.context_warning
        return "\n".join(result)


# ---------------------------------------------------------------------------
# Detect which MCP server variant we're connected to
# ---------------------------------------------------------------------------

def _is_remote_server(manager: "MCPClientManager") -> bool:
    """Check if the MCP server is the remote hosted version (has notion-fetch)."""
    all_tools = manager.get_all_tools()
    tool_names = {tool.name for _, tool in all_tools if _ == SERVER_NAME}
    return "notion-fetch" in tool_names


# ---------------------------------------------------------------------------
# Response formatting helpers
# ---------------------------------------------------------------------------

def _safe_parse(raw: str) -> Any:
    """Try to parse JSON from raw MCP response. Returns dict/list or None."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _check_error(data: dict | None, raw: str) -> str | None:
    """Check if a Notion API response is an error and return a clear message."""
    if data and isinstance(data, dict):
        if data.get("object") == "error" or (
            "status" in data and isinstance(data.get("status"), int) and data["status"] >= 400
        ):
            code = data.get("code", "unknown")
            message = data.get("message", "Unknown error")
            status = data.get("status", "?")

            if code == "object_not_found":
                return (
                    f"Error: Not found (HTTP {status}). {message} "
                    "Try using notion_search to find the correct ID first."
                )
            if code == "unauthorized" or status == 401:
                return (
                    f"Error: Unauthorized (HTTP {status}). "
                    "The Notion API token may be invalid or the page/database "
                    "is not shared with the integration. Tell the user about this error."
                )
            if code == "validation_error":
                return f"Error: Invalid request. {message}"
            if code == "rate_limited":
                return "Error: Rate limited by Notion. Please wait a moment and try again."
            return f"Error: {code} (HTTP {status}). {message}"

    # Check for raw error strings from MCP client
    if raw and isinstance(raw, str) and raw.startswith("Error"):
        return raw[:300]

    return None


def _extract_page_id(page_id_or_url: str) -> str:
    """Extract a Notion page ID from a URL or raw ID string."""
    s = page_id_or_url.strip()

    if "notion.so" in s or "notion.site" in s:
        s = s.split("?")[0].split("#")[0]
        match = re.search(r"([a-f0-9]{32})$", s.replace("-", ""))
        if match:
            return match.group(1)
        parts = s.rstrip("/").split("/")
        for part in reversed(parts):
            clean = part.replace("-", "")
            match = re.search(r"([a-f0-9]{32})$", clean)
            if match:
                return match.group(1)

    clean = s.replace("-", "")
    if re.match(r"^[a-f0-9]{32}$", clean):
        return clean

    return s


def _truncate(text: str, max_chars: int = MAX_RESPONSE_CHARS) -> str:
    """Truncate text and add indicator if needed."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n... (truncated, use more specific queries to get details)"


def _generate_context_warning(markdown_length: int, should_chunk: bool = False) -> str | None:
    """Generate tiered context warning based on markdown size.

    Returns None if no warning needed, otherwise returns warning message.
    If should_chunk is True, provides automatic chunking instructions.
    """
    if markdown_length <= 8000:
        return None  # No warning needed
    elif should_chunk and markdown_length > CHUNK_SIZE_THRESHOLD:
        return (
            f"This page is {markdown_length:,} characters (>{CHUNK_SIZE_THRESHOLD:,} threshold). "
            f"For small LLMs like GPT-5-nano, this page will be AUTOMATICALLY CHUNKED. "
            f"To analyze this page:\n"
            f"1. Ask for a specific section: 'Summarize the AI Summary section' or 'What are the action items?'\n"
            f"2. Or spawn subagents: Use the spawn tool to process sections in parallel\n"
            f"3. Or request auto-chunking: 'Process this page in chunks'\n\n"
            f"Available sections: AI Summary, Transcript, Notes, Action Items"
        )
    elif markdown_length <= 20000:
        return (
            f"This page is {markdown_length:,} characters. Consider spawning subagents "
            "to process sections in parallel (e.g., one for summary, one for transcript)."
        )
    elif markdown_length <= 50000:
        return (
            f"This page is {markdown_length:,} characters. RECOMMENDED: Spawn subagents "
            "to process different sections independently for better context management."
        )
    else:
        return (
            f"This page is {markdown_length:,} characters. STRONGLY RECOMMENDED: Spawn multiple "
            "subagents by section (summary, transcript, detailed findings, etc.) for optimal processing."
        )


def _format_id(notion_id: str) -> str:
    """Shorten Notion IDs for display (keep first 12 chars)."""
    return notion_id.replace("-", "")[:12] if notion_id else "?"


def _clean_enhanced_markdown(text: str) -> str:
    """Convert Notion's enhanced markdown (XML format) to clean markdown.

    Removes XML tags, converts mention-page tags to links, strips footnotes,
    and extracts properties to readable format.
    """
    import re

    # Extract properties from <properties> JSON tag
    properties_match = re.search(r'<properties>\s*({.*?})\s*</properties>', text, re.DOTALL)
    properties_text = ""
    if properties_match:
        try:
            props_json = _safe_parse(properties_match.group(1))
            if props_json and isinstance(props_json, dict):
                prop_lines = []
                for key, value in props_json.items():
                    # Skip internal fields
                    if key.startswith("date:") or key in ["url"]:
                        continue
                    # Format attendees as list
                    if key == "Attendees" and isinstance(value, list):
                        prop_lines.append(f"**{key}**: {len(value)} attendees")
                    elif isinstance(value, str):
                        prop_lines.append(f"**{key}**: {value}")
                if prop_lines:
                    properties_text = "\n" + "\n".join(prop_lines) + "\n"
        except Exception:
            pass

    # Remove XML wrapper tags
    text = re.sub(r'<page url="{{.*?}}"[^>]*>', '', text)
    text = re.sub(r'</page>', '', text)
    text = re.sub(r'<ancestor-path>.*?</ancestor-path>', '', text, flags=re.DOTALL)
    text = re.sub(r'<properties>.*?</properties>', properties_text, text, flags=re.DOTALL)
    text = re.sub(r'<content>', '', text)
    text = re.sub(r'</content>', '', text)

    # Clean meeting-notes tags
    text = re.sub(r'<meeting-notes>', '', text)
    text = re.sub(r'</meeting-notes>', '', text)

    # Clean summary/notes/transcript wrapper tags
    text = re.sub(r'<summary>', '\n## AI Summary\n', text)
    text = re.sub(r'</summary>', '', text)
    text = re.sub(r'<notes>', '\n## Notes\n', text)
    text = re.sub(r'</notes>', '', text)
    text = re.sub(r'<transcript>', '\n## Transcript\n', text)
    text = re.sub(r'</transcript>', '', text)

    # Convert <mention-page> to markdown links (keep just the section name)
    text = re.sub(r'<mention-page url="{{https://www\.notion\.so/([^"}]+)}}"/>', r'[\1]', text)

    # Convert <mention-date> to just the date
    text = re.sub(r'<mention-date start="([^"]+)"/>', r'\1', text)

    # Remove footnote references [^{{{{...}}}}]
    text = re.sub(r'\s*\[\^{{{{.*?}}}}\]', '', text)

    # Remove image tags (keep just a marker)
    text = re.sub(r'<image source="[^"]*"></image>', '[Image]', text)

    # Remove empty block markers (these indicate missing/unsupported content)
    text = re.sub(r'<empty-block/>\s*', '', text)

    # Clean up metadata header
    text = re.sub(r'Here is the result of "view" for the Page with URL.*?as of.*?\n', '', text)

    # Remove extra blank lines
    text = re.sub(r'\n\n\n+', '\n\n', text)

    # Clean up tabs
    text = re.sub(r'\t+', '', text)

    return text.strip()


def _extract_section(text: str, section_name: str) -> str | None:
    """Extract a specific section from cleaned markdown.

    Sections include: "AI Summary", "Transcript", "Notes", "Action Items"
    Returns the section content or None if not found.
    """
    import re

    # Define section markers
    section_markers = {
        "AI Summary": r"## AI Summary",
        "Transcript": r"## Transcript",
        "Notes": r"## Notes",
        "Action Items": r"### Action Items",
        "Participants": r"### Participants",
    }

    marker = section_markers.get(section_name)
    if not marker:
        return None

    # Find the section
    pattern = rf'{marker}\s*\n(.*?)(?=\n##|\Z)'
    match = re.search(pattern, text, re.DOTALL)

    if match:
        return match.group(1).strip()

    return None


def _extract_ai_section_info(text: str) -> dict:
    """Analyze AI summary and transcript sections for size/completeness.

    Returns dict with stats about extracted AI content:
    - summary_chars: Length of AI summary section
    - summary_words: Word count in summary
    - transcript_chars: Length of transcript section
    - transcript_words: Word count in transcript
    - speaker_lines: Number of transcript lines with speaker (contains ":")
    """
    info = {}

    # Extract summary if present
    if "## AI Summary" in text:
        parts = text.split("## AI Summary", 1)
        if len(parts) > 1:
            summary = parts[1].split("\n\n", 1)[0]  # Get until next section
            summary = summary.strip()
            info["summary_chars"] = len(summary)
            info["summary_words"] = len(summary.split())
        else:
            info["summary_chars"] = 0
            info["summary_words"] = 0

    # Extract transcript if present
    if "## Transcript" in text:
        parts = text.split("## Transcript", 1)
        if len(parts) > 1:
            transcript = parts[1]
            # Stop at next section (marked by \n\n# or \n\n##)
            for sep in ["\n\n# ", "\n\n## "]:
                if sep in transcript:
                    transcript = transcript.split(sep)[0]
                    break
            transcript = transcript.strip()
            info["transcript_chars"] = len(transcript)
            info["transcript_words"] = len(transcript.split())
            info["speaker_lines"] = len([l for l in transcript.split("\n") if ":" in l and len(l) < 200])
        else:
            info["transcript_chars"] = 0
            info["transcript_words"] = 0
            info["speaker_lines"] = 0

    return info


# ---------------------------------------------------------------------------
# Remote server response compression
# ---------------------------------------------------------------------------

def _build_fetch_response(raw: str) -> NotionResponse:
    """Convert remote notion-fetch response to structured NotionResponse.

    The remote server returns JSON with a 'text' field containing enhanced
    markdown, including meeting AI summaries and transcripts.
    """
    data = _safe_parse(raw)
    if not data or not isinstance(data, dict):
        return NotionResponse(markdown=_truncate(raw), success=False)

    # Check for errors in the response
    err = _check_error(data, raw)
    if err:
        return NotionResponse(markdown=err, success=False)

    # The remote server returns {"metadata": {...}, "title": "...", "text": "..."}
    text = data.get("text", "")
    title = data.get("title", "")
    metadata = data.get("metadata", {})

    if not text:
        empty_msg = f"Page '{title}' has no content." if title else "No content returned."
        return NotionResponse(markdown=empty_msg, success=True, completeness_percentage=0)

    # Build markdown output with title
    markdown_lines = []
    if title:
        markdown_lines.append(f"# {title}\n")

    # Add AI content sections if present (meeting summary, transcript)
    if "AI Summary" in text or "Transcript" in text:
        # The text already contains these sections from remote server
        pass

    # Clean the enhanced markdown (remove XML tags, footnotes, etc.)
    cleaned_text = _clean_enhanced_markdown(text)

    markdown_lines.append(cleaned_text)
    full_markdown = "\n".join(markdown_lines)

    # Calculate completeness - remote server is very complete
    compression_ratio = len(text) / len(raw) if raw else 1.0
    completeness = 95 if compression_ratio > 0.1 else 80

    # Check if we need to chunk this for small LLMs
    should_chunk = len(full_markdown) > CHUNK_SIZE_THRESHOLD

    # Generate tiered context warning based on size (no truncation)
    context_warning = _generate_context_warning(len(full_markdown), should_chunk=should_chunk)

    # Analyze AI content for detailed statistics
    ai_info = _extract_ai_section_info(text)

    breakdown = {
        "raw_json_chars": len(raw),
        "markdown_chars": len(full_markdown),
        "compression_ratio": f"{(len(full_markdown)/len(raw)*100 if raw else 0):.1f}%",
        "ai_content": "meeting summary/transcript included" if "Transcript" in text or "Summary" in text else "none",
        "ai_section_sizes": {
            "summary_chars": ai_info.get("summary_chars", 0),
            "summary_words": ai_info.get("summary_words", 0),
            "transcript_chars": ai_info.get("transcript_chars", 0),
            "transcript_words": ai_info.get("transcript_words", 0),
            "transcript_speaker_lines": ai_info.get("speaker_lines", 0),
        },
    }

    # Build detailed log message with AI section stats
    ai_log_parts = []
    if ai_info.get("summary_chars", 0) > 0:
        ai_log_parts.append(f"summary: {ai_info['summary_chars']} chars ({ai_info['summary_words']} words)")
    if ai_info.get("transcript_chars", 0) > 0:
        ai_log_parts.append(f"transcript: {ai_info['transcript_chars']} chars ({ai_info['transcript_words']} words, {ai_info['speaker_lines']} speakers)")

    ai_log = f". AI content: {', '.join(ai_log_parts)}" if ai_log_parts else ""

    return NotionResponse(
        markdown=full_markdown,  # Return FULL markdown, no truncation
        success=True,
        completeness_percentage=completeness,
        completeness_breakdown=breakdown,
        context_warning=context_warning,
        log=f"Fetched remote page '{title}': {len(raw)} bytes → {len(full_markdown)} chars markdown{ai_log}",
    )


def _compress_search_response(raw: str) -> str:
    """Compress the remote notion-search response for small LLMs.

    The remote server returns {"results": [...]} where each result has:
    title, url, type, highlight, timestamp, id.
    """
    data = _safe_parse(raw)
    if not data:
        return _truncate(raw)

    err = _check_error(data, raw)
    if err:
        return err

    # Remote search returns the text directly (some versions)
    if isinstance(data, dict) and "text" in data:
        return _truncate(data["text"])

    # Remote search returns {"results": [{title, url, type, id, ...}, ...]}
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
        if not results:
            return "No results found."

        # Detect format: remote results have "title" at top level
        if isinstance(results[0], dict) and "title" in results[0]:
            return _compress_remote_search_results(results)
        else:
            # Local API format (has "properties")
            return _compress_local_search_results(data)

    return _truncate(raw)


def _compress_remote_search_results(results: list[dict]) -> str:
    """Compress remote notion-search results into a concise list."""
    lines = [f"Found {len(results)} result(s):\n"]
    for i, item in enumerate(results[:15], 1):
        title = item.get("title", "(untitled)")
        obj_type = item.get("type", "page")
        item_id = item.get("id", "")
        timestamp = item.get("timestamp", "")

        # Determine a display type
        display_type = obj_type
        if "database" in obj_type.lower() or "data_source" in obj_type.lower():
            display_type = "database"
        elif "calendar" in obj_type.lower():
            display_type = "calendar"

        line = f"{i}. [{display_type}] \"{title}\" (id: {item_id})"
        if timestamp:
            line += f"  {timestamp}"
        lines.append(line)

    if len(results) > 15:
        lines.append(f"\n... and {len(results) - 15} more results")

    return _truncate("\n".join(lines))


def _compress_local_search_results(data: dict) -> str:
    """Compress local API search results into a concise list."""
    results = data.get("results", [])
    if not results:
        return "No results found."

    lines = [f"Found {len(results)} result(s):\n"]
    for i, item in enumerate(results[:15], 1):
        obj_type = item.get("object", "page")
        title = _extract_title_from_local(item)
        item_id = item.get("id", "")
        last_edited = item.get("last_edited_time", "")[:10]
        lines.append(
            f"{i}. [{obj_type}] \"{title}\" (id: {item_id})"
            + (f"  edited: {last_edited}" if last_edited else "")
        )

    if len(results) > 15:
        lines.append(f"\n... and {len(results) - 15} more results")

    return _truncate("\n".join(lines))


def _extract_title_from_local(page: dict) -> str:
    """Extract title from a local API page/database object."""
    props = page.get("properties", {})
    for key in ("Name", "name", "Title", "title"):
        prop = props.get(key, {})
        title_arr = prop.get("title", [])
        if title_arr and isinstance(title_arr, list):
            return "".join(t.get("plain_text", "") for t in title_arr)
    title_arr = page.get("title", [])
    if title_arr and isinstance(title_arr, list):
        return "".join(t.get("plain_text", "") for t in title_arr)
    return "(untitled)"


def _extract_property_value(prop: dict) -> str:
    """Extract a human-readable value from a Notion property object."""
    ptype = prop.get("type", "")

    if ptype == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    if ptype == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    if ptype == "number":
        v = prop.get("number")
        return str(v) if v is not None else ""
    if ptype == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if ptype == "multi_select":
        return ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
    if ptype == "date":
        d = prop.get("date")
        if d:
            start = d.get("start", "")
            end = d.get("end", "")
            return f"{start} → {end}" if end else start
        return ""
    if ptype == "checkbox":
        return "Yes" if prop.get("checkbox") else "No"
    if ptype == "status":
        s = prop.get("status")
        return s.get("name", "") if s else ""
    if ptype == "url":
        return prop.get("url", "")
    if ptype == "email":
        return prop.get("email", "")
    if ptype == "phone_number":
        return prop.get("phone_number", "")
    if ptype == "formula":
        f = prop.get("formula", {})
        return str(f.get(f.get("type", ""), ""))
    if ptype == "relation":
        return f"({len(prop.get('relation', []))} relations)"
    if ptype == "rollup":
        r = prop.get("rollup", {})
        return str(r.get(r.get("type", ""), ""))
    if ptype == "people":
        return ", ".join(p.get("name", "?") for p in prop.get("people", []))
    if ptype == "created_time":
        return prop.get("created_time", "")
    if ptype == "last_edited_time":
        return prop.get("last_edited_time", "")
    if ptype == "created_by":
        return prop.get("created_by", {}).get("name", "")
    if ptype == "last_edited_by":
        return prop.get("last_edited_by", {}).get("name", "")

    return f"({ptype})"


def _format_property_for_markdown(prop_name: str, prop: dict) -> str:
    """Format a Notion property into markdown-friendly text with proper formatting."""
    ptype = prop.get("type", "")

    if ptype == "title":
        text = "".join(t.get("plain_text", "") for t in prop.get("title", []))
        return f"**{text}**"

    if ptype == "rich_text":
        return _format_rich_text(prop.get("rich_text", []))

    if ptype == "number":
        v = prop.get("number")
        return str(v) if v is not None else ""

    if ptype == "select":
        sel = prop.get("select")
        return f"`{sel.get('name', '')}`" if sel else ""

    if ptype == "multi_select":
        tags = [f"`{s.get('name', '')}`" for s in prop.get("multi_select", [])]
        return ", ".join(tags) if tags else ""

    if ptype == "date":
        d = prop.get("date")
        if d:
            start = d.get("start", "")
            end = d.get("end", "")
            if end:
                return f"{start} → {end}"
            return start
        return ""

    if ptype == "checkbox":
        checked = prop.get("checkbox")
        return "✓ Done" if checked else "☐ Pending"

    if ptype == "status":
        s = prop.get("status")
        return f"`{s.get('name', '')}`" if s else ""

    if ptype == "url":
        url = prop.get("url", "")
        return f"[Link]({url})" if url else ""

    if ptype == "email":
        email = prop.get("email", "")
        return f"`{email}`" if email else ""

    if ptype == "phone_number":
        phone = prop.get("phone_number", "")
        return f"`{phone}`" if phone else ""

    if ptype == "formula":
        f = prop.get("formula", {})
        result = f.get(f.get("type", ""), "")
        return f"__{result}__" if result else ""

    if ptype == "relation":
        relations = prop.get("relation", [])
        count = len(relations)
        return f"→ {count} related item{'s' if count != 1 else ''}"

    if ptype == "rollup":
        r = prop.get("rollup", {})
        result = r.get(r.get("type", ""), "")
        return str(result) if result else ""

    if ptype == "people":
        people = [f"@{p.get('name', '?')}" for p in prop.get("people", [])]
        return ", ".join(people) if people else ""

    if ptype == "created_time":
        return prop.get("created_time", "")

    if ptype == "last_edited_time":
        return prop.get("last_edited_time", "")

    if ptype == "created_by":
        creator = prop.get("created_by", {})
        return f"@{creator.get('name', '?')}"

    if ptype == "last_edited_by":
        editor = prop.get("last_edited_by", {})
        return f"@{editor.get('name', '?')}"

    return ""


def _format_rich_text(rich_text_arr: list[dict]) -> str:
    """Convert Notion rich_text array to markdown with formatting."""
    result = []
    for item in rich_text_arr:
        text = item.get("plain_text", "")
        if not text:
            continue

        annotations = item.get("annotations", {})

        # Apply markdown formatting
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("code"):
            text = f"`{text}`"
        if annotations.get("strikethrough"):
            text = f"~~{text}~~"
        if annotations.get("underline"):
            # Markdown doesn't support underline, use emphasis
            text = f"<u>{text}</u>"

        # Handle links
        href = item.get("href")
        if href:
            text = f"[{text}]({href})"

        # Handle colors/highlights via HTML comments (preserved for future rendering)
        if annotations.get("color") != "default":
            color = annotations.get("color", "default")
            text = f"<!-- color:{color} -->{text}"

        result.append(text)

    return "".join(result)


def _blocks_to_markdown(blocks: list[dict]) -> str:
    """Convert Notion block objects to readable markdown (local API only)."""
    lines = []
    for block in blocks:
        btype = block.get("type", "")
        data = block.get(btype, {})
        text_parts = data.get("rich_text", [])
        text = "".join(t.get("plain_text", "") for t in text_parts) if text_parts else ""

        if btype == "paragraph":
            lines.append(text)
        elif btype.startswith("heading_"):
            level = btype[-1]
            lines.append(f"{'#' * int(level)} {text}")
        elif btype == "bulleted_list_item":
            lines.append(f"- {text}")
        elif btype == "numbered_list_item":
            lines.append(f"1. {text}")
        elif btype == "to_do":
            checked = "x" if data.get("checked") else " "
            lines.append(f"- [{checked}] {text}")
        elif btype == "code":
            lang = data.get("language", "")
            lines.append(f"```{lang}\n{text}\n```")
        elif btype == "quote":
            lines.append(f"> {text}")
        elif btype == "divider":
            lines.append("---")
        elif btype == "callout":
            icon = data.get("icon", {}).get("emoji", "")
            lines.append(f"{icon} {text}")
        elif btype == "toggle":
            lines.append(f"▸ {text}")
        elif btype == "child_page":
            lines.append(f"📄 {data.get('title', '(subpage)')}")
        elif btype == "child_database":
            lines.append(f"🗄 {data.get('title', '(database)')}")
        elif text:
            lines.append(text)

    return "\n".join(lines)


def _markdown_to_blocks(text: str) -> list[dict]:
    """Convert simple markdown text to Notion block objects (local API only)."""
    blocks = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            lang = line[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append({
                "object": "block", "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                    "language": lang or "plain text",
                },
            })
            i += 1
            continue

        if line.startswith("### "):
            blocks.append(_text_block("heading_3", line[4:]))
        elif line.startswith("## "):
            blocks.append(_text_block("heading_2", line[3:]))
        elif line.startswith("# "):
            blocks.append(_text_block("heading_1", line[2:]))
        elif line.startswith("- [x] ") or line.startswith("- [ ] "):
            checked = line[3] == "x"
            blocks.append({
                "object": "block", "type": "to_do",
                "to_do": {
                    "rich_text": [{"type": "text", "text": {"content": line[6:]}}],
                    "checked": checked,
                },
            })
        elif line.startswith("- ") or line.startswith("* "):
            blocks.append(_text_block("bulleted_list_item", line[2:]))
        elif len(line) > 2 and line[0].isdigit() and line[1] in (".", ")"):
            blocks.append(_text_block("numbered_list_item", line[2:].lstrip()))
        elif len(line) > 3 and line[:2].isdigit() and line[2] in (".", ")"):
            blocks.append(_text_block("numbered_list_item", line[3:].lstrip()))
        elif line.strip() in ("---", "***", "___"):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        elif line.startswith("> "):
            blocks.append(_text_block("quote", line[2:]))
        elif line.strip():
            blocks.append(_text_block("paragraph", line))

        i += 1

    return blocks


def _text_block(block_type: str, text: str) -> dict:
    """Create a simple Notion block with text content."""
    return {
        "object": "block", "type": block_type,
        block_type: {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


# ---------------------------------------------------------------------------
# Semantic wrapper tools
# ---------------------------------------------------------------------------

class NotionSearchTool(Tool):
    """Search Notion pages and databases by keyword."""

    name = "notion_search"
    description = (
        "Search Notion for pages and databases matching a query. "
        "Returns a list of titles and IDs. Use the ID with other notion tools."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g. 'meeting notes', 'project tracker')",
            },
        },
        "required": ["query"],
    }

    def __init__(self, manager: "MCPClientManager", is_remote: bool = False):
        self._manager = manager
        self._is_remote = is_remote

    async def execute(self, query: str, **kwargs: Any) -> str:
        logger.info(f"[notion_search] Searching for: {query}")

        if self._is_remote:
            raw = await self._manager.call_tool(
                SERVER_NAME, "notion-search", {"query": query}
            )
        else:
            raw = await self._manager.call_tool(
                SERVER_NAME, "API-post-search", {"query": query}
            )

        raw_len = len(raw) if raw else 0
        logger.debug(f"[notion_search] Raw response: {raw_len} chars")

        if self._is_remote:
            result = _compress_search_response(raw)
        else:
            data = _safe_parse(raw)
            err = _check_error(data, raw)
            if err:
                logger.warning(f"[notion_search] API error: {err}")
                return err
            if not data or "results" not in data:
                return _truncate(raw)
            result = _compress_local_search_results(data)

        logger.info(
            f"[notion_search] Compressed: {raw_len} chars → {len(result)} chars"
        )
        return result


class NotionReadPageTool(Tool):
    """Read a Notion page's properties, content, and meeting transcripts."""

    name = "notion_read_page"
    description = (
        "Read a Notion page. Returns the page title, properties, and content "
        "as markdown. Accepts a page_id OR a full Notion URL. "
        "For meeting pages, includes AI summaries and transcripts."
    )
    parameters = {
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Notion page ID (32-char hex) or a full notion.so URL",
            },
            "include_transcript": {
                "type": "boolean",
                "description": "Include meeting transcript if available (default: true)",
            },
        },
        "required": ["page_id"],
    }

    def __init__(self, manager: "MCPClientManager", is_remote: bool = False):
        self._manager = manager
        self._is_remote = is_remote

    async def execute(self, page_id: str, include_transcript: bool = True, **kwargs: Any) -> str:
        original_input = page_id
        page_id = _extract_page_id(page_id)
        if original_input != page_id:
            logger.info(f"[notion_read_page] Extracted ID '{page_id}' from URL")
        logger.info(f"[notion_read_page] Reading page: {page_id}")

        if self._is_remote:
            return await self._execute_remote(page_id, include_transcript)
        else:
            return await self._execute_local(page_id)

    async def _execute_remote(self, page_id: str, include_transcript: bool) -> str:
        """Use the remote notion-fetch tool (includes transcripts).

        If the response is truncated (completeness < 90%, or suspicious content patterns),
        automatically falls back to block-by-block fetching using the Notion API pagination
        pattern.
        """
        args: dict[str, Any] = {"id": page_id}
        if include_transcript:
            args["include_transcript"] = True

        raw = await self._manager.call_tool(SERVER_NAME, "notion-fetch", args)
        raw_len = len(raw) if raw else 0
        logger.debug(f"[notion_read_page] Raw response: {raw_len} chars")

        response = _build_fetch_response(raw)

        # Check for severe truncation (< 80% completeness indicates serious issues)
        # Note: We don't fall back for minor truncation (~97%) because the local server
        # cannot read meeting transcripts at all - better to get 97% than 0%
        completeness_pct = response.completeness['percentage']
        if completeness_pct < 80:
            logger.warning(
                f"[notion_read_page] Severe truncation detected (completeness: {completeness_pct:.0f}%). "
                f"Falling back to block pagination..."
            )
            # Fall back to local API with block pagination for complete content
            return await self._execute_with_block_pagination(page_id)

        result = response.to_string()
        logger.info(
            f"[notion_read_page] Remote: {raw_len} bytes → {len(result)} chars with completeness {completeness_pct:.0f}%"
        )
        return result

    async def _execute_with_block_pagination(self, page_id: str) -> str:
        """Fetch page content using block-by-block pagination (handles large pages).

        Uses Notion API pagination pattern via the local MCP server:
        fetch blocks in 100-block chunks until has_more=False, then reassemble
        complete content. This bypasses the ~25KB response cap of the remote
        notion-fetch tool.
        """
        logger.info(f"[notion_read_page] Using block pagination for page {page_id}")

        # Use the local server for pagination (notion-local, not notion)
        local_server = "notion-local"

        # Step 1: Get page metadata (title, properties)
        raw_page = await self._manager.call_tool(
            local_server, "API-retrieve-a-page", {"page_id": page_id}
        )
        page_data = _safe_parse(raw_page)
        err = _check_error(page_data, raw_page)
        if err:
            logger.error(f"[notion_read_page] Failed to fetch page metadata: {err}")
            return f"Error fetching page: {err}"

        # Extract title from local API format
        title = _extract_title_from_local(page_data)

        # Step 2: Fetch ALL blocks with pagination (100 blocks per request)
        all_blocks = []
        has_more = True
        start_cursor = None
        total_requests = 0
        max_requests = 50  # Safety limit (50 requests × 100 blocks = 5,000 blocks max)

        while has_more and total_requests < max_requests:
            # Build args for block fetch
            args: dict[str, Any] = {"block_id": page_id, "page_size": 100}
            if start_cursor:
                args["start_cursor"] = start_cursor

            # Fetch next page of blocks from local server
            raw_blocks = await self._manager.call_tool(
                local_server, "API-get-block-children", args
            )
            blocks_data = _safe_parse(raw_blocks)

            if not blocks_data or not isinstance(blocks_data, dict):
                logger.warning(f"[notion_read_page] Invalid block response on request {total_requests + 1}")
                break

            # Append results
            results = blocks_data.get("results", [])
            all_blocks.extend(results)
            has_more = blocks_data.get("has_more", False)
            start_cursor = blocks_data.get("next_cursor")
            total_requests += 1

            logger.debug(
                f"[notion_read_page] Fetched {len(results)} blocks "
                f"(total: {len(all_blocks)}, has_more: {has_more})"
            )

        # Step 3: Extract properties from page metadata
        props_lines = []
        if page_data and isinstance(page_data, dict):
            props = page_data.get("properties", {})
            if props:
                props_lines.append("\n**Properties:**")
                for prop_name, prop_val in props.items():
                    if prop_name.lower() in ("name", "title"):
                        continue
                    value = _extract_property_value(prop_val)
                    if value:
                        props_lines.append(f"- {prop_name}: {value}")

        # Step 4: Convert all blocks to markdown
        content_markdown = _blocks_to_markdown(all_blocks)

        # Step 5: Assemble complete page
        lines = [f"# {title}"]
        if props_lines:
            lines.extend(props_lines)
        if content_markdown.strip():
            lines.append("\n---\n")
            lines.append(content_markdown)

        full_markdown = "\n".join(lines)

        # Step 6: Analyze AI content (if present)
        ai_info = _extract_ai_section_info(full_markdown)

        # Step 7: Create response
        context_warning = _generate_context_warning(len(full_markdown))
        breakdown = {
            "source": "block_pagination",
            "blocks_fetched": len(all_blocks),
            "pagination_requests": total_requests,
            "markdown_chars": len(full_markdown),
            "ai_section_sizes": ai_info,
        }

        response = NotionResponse(
            markdown=full_markdown,
            success=True,
            completeness_percentage=100,  # Complete fetch via pagination
            completeness_breakdown=breakdown,
            context_warning=context_warning,
            log=f"Fetched page via block pagination: {len(all_blocks)} blocks in {total_requests} requests → {len(full_markdown)} chars",
        )

        logger.info(
            f"[notion_read_page] Block pagination complete: {len(all_blocks)} blocks, "
            f"{total_requests} requests, {len(full_markdown)} chars markdown"
        )
        return response.to_string()

    async def _execute_local(self, page_id: str) -> str:
        """Use the local API tools (fallback, no transcript support)."""
        # Step 1: Get page properties
        raw_page = await self._manager.call_tool(
            SERVER_NAME, "API-retrieve-a-page", {"page_id": page_id}
        )
        raw_page_len = len(raw_page) if raw_page else 0
        page_data = _safe_parse(raw_page)

        err = _check_error(page_data, raw_page)
        if err:
            logger.warning(f"[notion_read_page] API error: {err}")
            return err

        lines = []
        if page_data and isinstance(page_data, dict):
            title = _extract_title_from_local(page_data)
            lines.append(f"# {title}")
            props = page_data.get("properties", {})
            if props:
                lines.append("\n**Properties:**")
                for prop_name, prop_val in props.items():
                    if prop_name.lower() in ("name", "title"):
                        continue
                    value = _extract_property_value(prop_val)
                    if value:
                        lines.append(f"- {prop_name}: {value}")
            last_edited = page_data.get("last_edited_time", "")[:10]
            if last_edited:
                lines.append(f"\nLast edited: {last_edited}")
        else:
            lines.append(f"Page {page_id}:")
            lines.append(raw_page[:500])

        # Step 2: Get content blocks
        raw_blocks = await self._manager.call_tool(
            SERVER_NAME, "API-get-block-children", {"block_id": page_id}
        )
        raw_blocks_len = len(raw_blocks) if raw_blocks else 0
        blocks_data = _safe_parse(raw_blocks)
        if blocks_data and "results" in blocks_data:
            content = _blocks_to_markdown(blocks_data["results"])
            if content.strip():
                lines.append("\n---\n")
                lines.append(content)

        total_raw = raw_page_len + raw_blocks_len
        full_markdown = "\n".join(lines)

        # Generate context warning (no truncation, return full markdown)
        context_warning = _generate_context_warning(len(full_markdown))

        # Create response with full markdown
        response = NotionResponse(
            markdown=full_markdown,  # Return FULL markdown, no truncation
            success=True,
            completeness_percentage=90,  # Local API is mostly complete
            completeness_breakdown={"source": "local_api", "blocks_processed": len(blocks_data.get("results", []))},
            context_warning=context_warning,
            log=f"Fetched local page: {total_raw} bytes → {len(full_markdown)} chars markdown",
        )
        logger.info(
            f"[notion_read_page] Local: {total_raw} bytes → {len(full_markdown)} chars, context_warning={bool(context_warning)}"
        )
        return response.to_string()


class NotionQueryDatabaseTool(Tool):
    """Query a Notion database and return a summary table."""

    name = "notion_query_database"
    description = (
        "Query a Notion database. Returns a summary of entries with their "
        "properties (title, status, dates, etc.). Does NOT return full page content. "
        "Use notion_read_page to read a specific entry. "
        "If a database URL returns 404, use notion_search to find the correct database ID. "
        "Max 20 entries per query. Use filters to narrow results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "database_id": {
                "type": "string",
                "description": "The Notion database ID (32-char hex) or URL. Use notion_search to find it if unknown.",
            },
            "filter": {
                "type": "object",
                "description": (
                    "Notion filter object. Examples: "
                    "Date filter: {\"property\": \"Date\", \"date\": {\"on_or_after\": \"2026-02-01\"}} "
                    "Status filter: {\"property\": \"Status\", \"status\": {\"equals\": \"Done\"}} "
                    "Combine with: {\"and\": [{...}, {...}]}"
                ),
            },
            "page_size": {
                "type": "integer",
                "description": "Max entries to return (1-20, default 10). Cannot exceed 20.",
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["database_id"],
    }

    def __init__(self, manager: "MCPClientManager", is_remote: bool = False):
        self._manager = manager
        self._is_remote = is_remote

    async def execute(
        self,
        database_id: str,
        filter: dict | None = None,
        page_size: int = 10,
        **kwargs: Any,
    ) -> str:
        database_id = _extract_page_id(database_id)
        logger.info(f"[notion_query_database] Querying database: {database_id}")

        if self._is_remote:
            return await self._execute_remote(database_id, filter, page_size)
        else:
            return await self._execute_local(database_id, filter, page_size)

    async def _execute_remote(self, database_id: str, filter: dict | None, page_size: int) -> str:
        """Use the remote notion-fetch to get database content.

        Note: The remote server's notion-fetch returns a markdown summary of
        the database. Server-side filtering/pagination is not supported — the
        filter and page_size parameters are silently ignored in remote mode.
        """
        if filter:
            logger.warning(
                "[notion_query_database] Filters are not supported in remote mode "
                "(notion-fetch). The filter parameter will be ignored."
            )
        raw = await self._manager.call_tool(
            SERVER_NAME, "notion-fetch", {"id": database_id}
        )
        raw_len = len(raw) if raw else 0
        logger.debug(f"[notion_query_database] Raw response: {raw_len} chars")

        result = _compress_fetch_response(raw)
        logger.info(
            f"[notion_query_database] Compressed: {raw_len} chars → {len(result)} chars markdown"
        )
        return result

    async def _execute_local(self, database_id: str, filter: dict | None, page_size: int) -> str:
        """Use the local API tools (fallback)."""
        if filter:
            logger.info(f"[notion_query_database] With filter: {json.dumps(filter)[:200]}")

        original_page_size = page_size
        page_size = min(max(page_size, 1), 20)
        if original_page_size != page_size:
            logger.warning(
                f"[notion_query_database] page_size capped: {original_page_size} → {page_size} (max 20)"
            )

        args: dict[str, Any] = {"data_source_id": database_id, "page_size": page_size}
        if filter:
            args["filter"] = filter

        raw = await self._manager.call_tool(SERVER_NAME, "API-query-data-source", args)
        raw_len = len(raw) if raw else 0
        data = _safe_parse(raw)

        err = _check_error(data, raw)
        if err:
            logger.warning(f"[notion_query_database] API error: {err}")
            return err

        if not data or "results" not in data:
            return _truncate(raw)

        results = data["results"]
        if not results:
            return "No entries found in this database."

        total = len(results)
        has_more = data.get("has_more", False)

        # Collect property names
        all_props: dict[str, bool] = {}
        for entry in results:
            for prop_name in entry.get("properties", {}):
                all_props[prop_name] = True

        priority = ["Name", "name", "Title", "title", "Status", "status", "Date", "date", "Due", "due"]
        ordered_props = []
        for p in priority:
            if p in all_props:
                ordered_props.append(p)
                del all_props[p]
        for p in list(all_props.keys()):
            if len(ordered_props) >= 6:
                break
            ordered_props.append(p)

        lines = [f"Database query: {total} entries" + (" (more available)" if has_more else "") + "\n"]
        header = "| " + " | ".join(ordered_props) + " | ID |"
        separator = "| " + " | ".join("---" for _ in ordered_props) + " | --- |"
        lines.append(header)
        lines.append(separator)

        for entry in results:
            props = entry.get("properties", {})
            row_values = []
            for prop_name in ordered_props:
                prop = props.get(prop_name, {})
                row_values.append(_extract_property_value(prop)[:50])
            entry_id = entry.get("id", "")
            row = "| " + " | ".join(row_values) + f" | {_format_id(entry_id)} |"
            lines.append(row)

        lines.append(f"\nUse notion_read_page with a page ID to read full content.")

        full_markdown = "\n".join(lines)

        # Generate context warning (no truncation, return full markdown)
        context_warning = _generate_context_warning(len(full_markdown))

        # Create response with full markdown
        response = NotionResponse(
            markdown=full_markdown,  # Return FULL markdown, no truncation
            success=True,
            completeness_percentage=85,  # Database queries are mostly complete
            completeness_breakdown={"entries": total, "properties_shown": len(ordered_props)},
            context_warning=context_warning,
            log=f"Queried database: {raw_len} bytes → {len(full_markdown)} chars markdown ({total} entries, {len(ordered_props)} columns)",
        )
        logger.info(
            f"[notion_query_database] Local: {raw_len} bytes → {len(full_markdown)} chars "
            f"({total} entries, {len(ordered_props)} columns), context_warning={bool(context_warning)}"
        )
        return response.to_string()


class NotionCreatePageTool(Tool):
    """Create a new page in Notion."""

    name = "notion_create_page"
    description = (
        "Create a new page in Notion under a parent page or database. "
        "Provide a title and optional markdown content."
    )
    parameters = {
        "type": "object",
        "properties": {
            "parent_id": {
                "type": "string",
                "description": "Parent page ID or database ID",
            },
            "parent_type": {
                "type": "string",
                "enum": ["database_id", "page_id"],
                "description": "Type of parent (default: database_id)",
            },
            "title": {
                "type": "string",
                "description": "Page title",
            },
            "content": {
                "type": "string",
                "description": "Optional page content in markdown",
            },
        },
        "required": ["parent_id", "title"],
    }

    def __init__(self, manager: "MCPClientManager", is_remote: bool = False):
        self._manager = manager
        self._is_remote = is_remote

    async def execute(
        self,
        parent_id: str,
        title: str,
        parent_type: str = "database_id",
        content: str | None = None,
        **kwargs: Any,
    ) -> str:
        logger.info(f"[notion_create_page] Creating page: '{title}' under {parent_type}={parent_id}")

        if self._is_remote:
            return await self._execute_remote(parent_id, title, parent_type, content)
        else:
            return await self._execute_local(parent_id, title, parent_type, content)

    async def _execute_remote(self, parent_id: str, title: str, parent_type: str, content: str | None) -> str:
        """Use the remote notion-create-pages tool."""
        args: dict[str, Any] = {
            "parent": {parent_type: parent_id},
            "pages": [{"title": title}],
        }
        if content:
            args["pages"][0]["content"] = content

        raw = await self._manager.call_tool(SERVER_NAME, "notion-create-pages", args)
        raw_len = len(raw) if raw else 0

        data = _safe_parse(raw)
        err = _check_error(data, raw)
        if err:
            logger.warning(f"[notion_create_page] API error: {err}")
            return err

        logger.info(f"[notion_create_page] Created page ({raw_len} chars response)")
        return _truncate(raw) if raw_len > 200 else (raw or f"Created page \"{title}\"")

    async def _execute_local(self, parent_id: str, title: str, parent_type: str, content: str | None) -> str:
        """Use the local API tools (fallback)."""
        args: dict[str, Any] = {
            "parent": {parent_type: parent_id},
            "properties": {"Name": {"title": [{"text": {"content": title}}]}},
        }
        if content:
            args["children"] = _markdown_to_blocks(content)

        raw = await self._manager.call_tool(SERVER_NAME, "API-post-page", args)
        data = _safe_parse(raw)

        err = _check_error(data, raw)
        if err:
            logger.warning(f"[notion_create_page] API error: {err}")
            return err

        if data and isinstance(data, dict) and "id" in data:
            page_id = data["id"]
            logger.info(f"[notion_create_page] Created page: {page_id}")
            return f"Created page \"{title}\" (id: {page_id})"

        return _truncate(raw)


class NotionUpdatePageTool(Tool):
    """Update an existing Notion page."""

    name = "notion_update_page"
    description = (
        "Update a Notion page. Can update properties and/or append content. "
        "To append content, provide markdown text in the 'content' field."
    )
    parameters = {
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "The page ID to update",
            },
            "properties": {
                "type": "object",
                "description": "Properties to update (Notion property format)",
            },
            "content": {
                "type": "string",
                "description": "Markdown content to append to the page",
            },
        },
        "required": ["page_id"],
    }

    def __init__(self, manager: "MCPClientManager", is_remote: bool = False):
        self._manager = manager
        self._is_remote = is_remote

    async def execute(
        self,
        page_id: str,
        properties: dict | None = None,
        content: str | None = None,
        **kwargs: Any,
    ) -> str:
        logger.info(f"[notion_update_page] Updating page: {page_id}")

        if self._is_remote:
            return await self._execute_remote(page_id, properties, content)
        else:
            return await self._execute_local(page_id, properties, content)

    async def _execute_remote(self, page_id: str, properties: dict | None, content: str | None) -> str:
        """Use the remote notion-update-page tool."""
        args: dict[str, Any] = {"page_id": page_id}
        if properties:
            args["properties"] = properties
        if content:
            args["content"] = content

        if not properties and not content:
            return "Nothing to update. Provide 'properties' and/or 'content'."

        raw = await self._manager.call_tool(SERVER_NAME, "notion-update-page", args)
        data = _safe_parse(raw)
        err = _check_error(data, raw)
        if err:
            logger.warning(f"[notion_update_page] API error: {err}")
            return err

        logger.info(f"[notion_update_page] Updated page: {page_id}")
        return f"Page {page_id} updated successfully."

    async def _execute_local(self, page_id: str, properties: dict | None, content: str | None) -> str:
        """Use the local API tools (fallback)."""
        results = []

        if properties:
            raw = await self._manager.call_tool(
                SERVER_NAME, "API-patch-page",
                {"page_id": page_id, "properties": properties},
            )
            data = _safe_parse(raw)
            err = _check_error(data, raw)
            if err:
                results.append(err)
            elif data and "id" in data:
                results.append("Properties updated.")
            else:
                results.append(f"Property update: {raw[:200]}")

        if content:
            blocks = _markdown_to_blocks(content)
            raw = await self._manager.call_tool(
                SERVER_NAME, "API-patch-block-children",
                {"block_id": page_id, "children": blocks},
            )
            data = _safe_parse(raw)
            err = _check_error(data, raw)
            if err:
                results.append(err)
            elif data and "results" in data:
                results.append(f"Appended {len(data['results'])} block(s).")
            else:
                results.append(f"Content append: {raw[:200]}")

        if not properties and not content:
            return "Nothing to update. Provide 'properties' and/or 'content'."

        return " ".join(results)


class NotionExtractSectionTool(Tool):
    """Extract a specific section from a large Notion page (for chunked processing)."""

    name = "notion_extract_section"
    description = (
        "Extract a specific section from a Notion page for focused analysis. "
        "Use this when a page is too large for your context window. "
        "Available sections: 'AI Summary', 'Transcript', 'Notes', 'Action Items', 'Participants'"
    )
    parameters = {
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Notion page ID or URL",
            },
            "section": {
                "type": "string",
                "enum": ["AI Summary", "Transcript", "Notes", "Action Items", "Participants"],
                "description": "Which section to extract",
            },
        },
        "required": ["page_id", "section"],
    }

    def __init__(self, manager: "MCPClientManager", is_remote: bool = False):
        self._manager = manager
        self._is_remote = is_remote

    async def execute(self, page_id: str, section: str, **kwargs: Any) -> str:
        """Extract a specific section from the page."""
        original_input = page_id
        page_id = _extract_page_id(page_id)
        if original_input != page_id:
            logger.info(f"[notion_extract_section] Extracted ID '{page_id}' from URL")

        logger.info(f"[notion_extract_section] Extracting '{section}' from page: {page_id}")

        # First, fetch the full page
        if self._is_remote:
            args: dict[str, Any] = {"id": page_id, "include_transcript": True}
            raw = await self._manager.call_tool(SERVER_NAME, "notion-fetch", args)
            data = _safe_parse(raw)

            if not data or not isinstance(data, dict):
                return f"Error: Could not fetch page {page_id}"

            text = data.get("text", "")
            title = data.get("title", "")

            # Clean the enhanced markdown
            cleaned_text = _clean_enhanced_markdown(text)

            # Extract the requested section
            section_content = _extract_section(cleaned_text, section)

            if not section_content:
                available = ["AI Summary", "Transcript", "Notes", "Action Items", "Participants"]
                return (
                    f"Section '{section}' not found in page '{title}'.\n\n"
                    f"Available sections: {', '.join(available)}\n\n"
                    f"Try: notion_extract_section(page_id='{page_id}', section='AI Summary')"
                )

            # Build response
            result = f"# {title}\n\n## {section}\n\n{section_content}"

            logger.info(
                f"[notion_extract_section] Extracted {len(section_content):,} chars "
                f"from '{section}' section"
            )

            return result
        else:
            return (
                "Section extraction is only available with the remote MCP server. "
                "The local server does not support this feature."
            )


# ---------------------------------------------------------------------------
# Module entry point
# ---------------------------------------------------------------------------

def get_tools(manager: "MCPClientManager") -> list[Tool]:
    """Return all Notion semantic wrapper tools.

    Auto-detects whether the remote (hosted) or local (stdio) MCP server
    is connected and configures wrappers accordingly.
    """
    is_remote = _is_remote_server(manager)
    mode = "remote (mcp.notion.com)" if is_remote else "local (stdio)"
    logger.info(f"[notion-wrappers] Detected {mode} MCP server")

    return [
        NotionSearchTool(manager, is_remote=is_remote),
        NotionReadPageTool(manager, is_remote=is_remote),
        NotionQueryDatabaseTool(manager, is_remote=is_remote),
        NotionCreatePageTool(manager, is_remote=is_remote),
        NotionUpdatePageTool(manager, is_remote=is_remote),
        NotionExtractSectionTool(manager, is_remote=is_remote),
    ]
