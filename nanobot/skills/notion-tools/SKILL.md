---
name: notion-tools
description: "Use Notion tools to search, read, create, and update pages and databases. Use when the user asks about Notion content, meetings, notes, databases, or wants to create/edit Notion pages."
always: true
---

# Notion Tools

Use these tools to interact with Notion. Tool names are simple and deterministic.

## Tool Reference

| Task | Tool | Key parameters |
|---|---|---|
| Search pages/databases | `notion_search` | `query` |
| Read a page | `notion_read_page` | `page_id` (accepts ID or full notion.so URL), optional `include_transcript` (default: true) |
| Query a database | `notion_query_database` | `database_id`, optional `filter`, `page_size` (max 20) |
| Create a page | `notion_create_page` | `parent_id`, `title`, optional `content` |
| Update a page | `notion_update_page` | `page_id`, optional `properties`, `content` |

## Common Patterns

### Find and read items from a database

1. `notion_search` with `query: "database name"` to find the database
2. Use the `id` from search results (look for `[data_source]` type)
3. `notion_query_database` with `database_id: "<id>"` to list entries (returns a summary table)
4. `notion_read_page` with `page_id: "<id>"` to read a specific entry's full content

### Query with date filter

Use Notion filter syntax for date ranges:

```json
{
  "and": [
    {"property": "Meeting Date", "date": {"on_or_after": "2026-02-01"}},
    {"property": "Meeting Date", "date": {"on_or_before": "2026-02-07"}}
  ]
}
```

Other date filters: `equals`, `before`, `after`, `past_week`, `next_week`

### Read a meeting page (with transcript)

1. `notion_search` with `query: "meeting name"` to find the meeting page
2. `notion_read_page` with `page_id: "<id>"` — transcripts and AI summaries are included automatically
3. To skip the transcript (shorter response), use `include_transcript: false`

### Search and read a page

1. `notion_search` with `query: "page name"` to find the page
2. `notion_read_page` with `page_id: "<id>"` to read its content

### Create a page in a database

1. `notion_search` to find the target database
2. `notion_create_page` with `parent_id: "<database_id>"`, `title`, and optional `content` (markdown)

## Important

- **When the user shares a notion.so URL, use `notion_read_page` with the full URL as the `page_id`.** Do NOT use web_fetch for Notion URLs.
- **Database URL IDs often don't match the database object ID.** If you get a 404, use `notion_search` to find the correct database ID. Look for results with type `[data_source]`.
- Notion IDs are 32-char hex strings like `2de5f57c2eef8044a3a7c2822e01765d`
- Database queries return max 20 entries per call. Use `filter` to narrow results rather than requesting large page sizes.
- Database queries return property summaries (titles, statuses, dates) — not full page content.
- Use `notion_read_page` to get the full content of a specific page.
- **Always use filters when the user asks for specific date ranges** (e.g., "last week", "this month"). Don't retrieve all entries and filter manually.
- **Meeting pages include AI summaries and transcripts automatically** via `notion_read_page`. No special steps needed.
