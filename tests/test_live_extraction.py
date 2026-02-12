#!/usr/bin/env python3
"""Test live extraction of the Weekly-Product-Sync page and compare with exported file."""

import asyncio
from nanobot.mcp.client import MCPClientManager
from nanobot.mcp.wrappers.notion import NotionReadPageTool, _is_remote_server
from nanobot.config.loader import load_config
from loguru import logger


async def test_live_extraction():
    """Extract the page and compare with exported file."""

    config = load_config()
    manager = MCPClientManager(config.mcp_servers)
    await manager.start()

    is_remote = _is_remote_server(manager)
    tool = NotionReadPageTool(manager, is_remote=is_remote)

    page_id = "3055f57c2eef8007945edbe3c6292606"

    logger.info("Fetching page from Notion...")
    result = await tool.execute(page_id=page_id, include_transcript=True)

    # Save to file for comparison
    output_file = "C:/Users/ekmun/Dev/nanobot/tests/extracted_page.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)

    logger.info(f"Saved extraction to: {output_file}")

    # Load exported file
    exported_file = r"C:\Users\ekmun\Downloads\0f09d7ae-3b23-4b0c-814f-046c9fd7aef6_ExportBlock-2c3fc12a-0c54-43e0-8475-fc0fbcf3db78\ExportBlock-2c3fc12a-0c54-43e0-8475-fc0fbcf3db78-Part-1\@Today Weekly Product Sync 3055f57c2eef8007945edbe3c6292606.md"

    with open(exported_file, "r", encoding="utf-8") as f:
        exported_content = f.read()

    # Analysis
    logger.info("\n" + "="*80)
    logger.info("COMPARISON ANALYSIS")
    logger.info("="*80)

    logger.info(f"\nExtracted size: {len(result):,} characters")
    logger.info(f"Exported size: {len(exported_content):,} characters")
    logger.info(f"Ratio: {len(result)/len(exported_content)*100:.1f}%")

    # Check for key sections
    sections_to_check = [
        ("Meeting Transcript and Notes", "## Meeting Transcript and Notes"),
        ("Summary section", "Summary"),
        ("GSOP section", "### GSOP"),
        ("Transcript section", "Transcript"),
        ("Action Items", "### Action Items"),
        ("Participants", "### Participants"),
    ]

    logger.info("\n" + "-"*80)
    logger.info("SECTION PRESENCE CHECK")
    logger.info("-"*80)

    for section_name, marker in sections_to_check:
        in_extracted = marker in result
        in_exported = marker in exported_content
        status = "✅" if in_extracted == in_exported else "❌"
        logger.info(f"{status} {section_name:30} | Extracted: {in_extracted:5} | Exported: {in_exported:5}")

    # Line count
    extracted_lines = result.count('\n')
    exported_lines = exported_content.count('\n')

    logger.info("\n" + "-"*80)
    logger.info("LINE COUNT")
    logger.info("-"*80)
    logger.info(f"Extracted: {extracted_lines:,} lines")
    logger.info(f"Exported: {exported_lines:,} lines (1,134 expected)")
    logger.info(f"Missing: {exported_lines - extracted_lines:,} lines ({(exported_lines - extracted_lines)/exported_lines*100:.1f}%)")

    # Check transcript length
    if "Transcript" in result and "Transcript" in exported_content:
        # Extract transcript portions
        extracted_transcript = result.split("Transcript", 1)[1] if "Transcript" in result else ""
        exported_transcript = exported_content.split("Transcript", 1)[1] if "Transcript" in exported_content else ""

        logger.info("\n" + "-"*80)
        logger.info("TRANSCRIPT ANALYSIS")
        logger.info("-"*80)
        logger.info(f"Extracted transcript: {len(extracted_transcript):,} chars")
        logger.info(f"Exported transcript: {len(exported_transcript):,} chars")
        logger.info(f"Ratio: {len(extracted_transcript)/len(exported_transcript)*100:.1f}%")

    # Show first difference
    logger.info("\n" + "-"*80)
    logger.info("FIRST 500 CHARS OF EACH")
    logger.info("-"*80)
    logger.info("\nExtracted:")
    logger.info(result[:500])
    logger.info("\nExported:")
    logger.info(exported_content[:500])

    await manager.stop()


if __name__ == "__main__":
    asyncio.run(test_live_extraction())
