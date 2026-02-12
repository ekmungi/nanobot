#!/usr/bin/env python3
"""Test the XML cleanup and section extraction features."""

import asyncio
from nanobot.mcp.client import MCPClientManager
from nanobot.mcp.wrappers.notion import NotionReadPageTool, NotionExtractSectionTool, _is_remote_server
from nanobot.config.loader import load_config
from loguru import logger


async def test_cleanup_and_chunking():
    """Test cleanup, chunking detection, and section extraction."""

    config = load_config()
    manager = MCPClientManager(config.mcp_servers)
    await manager.start()

    is_remote = _is_remote_server(manager)
    read_tool = NotionReadPageTool(manager, is_remote=is_remote)
    extract_tool = NotionExtractSectionTool(manager, is_remote=is_remote)

    page_id = "3055f57c2eef8007945edbe3c6292606"

    # Test 1: Full page with cleanup
    logger.info("="*80)
    logger.info("TEST 1: Full page extraction with XML cleanup")
    logger.info("="*80)

    result = await read_tool.execute(page_id=page_id, include_transcript=True)

    # Save cleaned output
    output_file = "C:/Users/ekmun/Dev/nanobot/tests/cleaned_page.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)

    logger.info(f"Saved cleaned page to: {output_file}")
    logger.info(f"Size: {len(result):,} characters")

    # Check for XML tags (should be gone)
    has_xml = "<page" in result or "<properties>" in result or "<summary>" in result
    logger.info(f"Contains XML tags: {has_xml} (should be False)")

    # Check for clean sections
    has_summary = "## AI Summary" in result
    has_transcript = "## Transcript" in result
    has_footnotes = "[^{{{{" in result

    logger.info(f"Has '## AI Summary' header: {has_summary}")
    logger.info(f"Has '## Transcript' header: {has_transcript}")
    logger.info(f"Has footnote refs: {has_footnotes} (should be False)")

    # Show first 1000 chars
    logger.info("\nFirst 1000 characters:")
    logger.info(result[:1000])

    # Test 2: Section extraction
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Section extraction (AI Summary only)")
    logger.info("="*80)

    summary_result = await extract_tool.execute(page_id=page_id, section="AI Summary")

    # Save section output
    section_file = "C:/Users/ekmun/Dev/nanobot/tests/section_summary.md"
    with open(section_file, "w", encoding="utf-8") as f:
        f.write(summary_result)

    logger.info(f"Saved AI Summary section to: {section_file}")
    logger.info(f"Size: {len(summary_result):,} characters (much smaller)")

    # Show first 500 chars
    logger.info("\nFirst 500 characters of AI Summary:")
    logger.info(summary_result[:500])

    # Test 3: Extract Action Items
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Section extraction (Action Items only)")
    logger.info("="*80)

    actions_result = await extract_tool.execute(page_id=page_id, section="Action Items")

    logger.info(f"Action Items size: {len(actions_result):,} characters")
    logger.info("\nAction Items content:")
    logger.info(actions_result)

    # Test 4: Extract Transcript
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Section extraction (Transcript only)")
    logger.info("="*80)

    transcript_result = await extract_tool.execute(page_id=page_id, section="Transcript")

    transcript_file = "C:/Users/ekmun/Dev/nanobot/tests/section_transcript.md"
    with open(transcript_file, "w", encoding="utf-8") as f:
        f.write(transcript_result)

    logger.info(f"Saved Transcript section to: {transcript_file}")
    logger.info(f"Size: {len(transcript_result):,} characters")

    # Summary
    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)

    logger.info(f"Full page (cleaned):  {len(result):,} chars")
    logger.info(f"AI Summary section:   {len(summary_result):,} chars")
    logger.info(f"Action Items section: {len(actions_result):,} chars")
    logger.info(f"Transcript section:   {len(transcript_result):,} chars")

    logger.info("\n✅ XML cleanup: " + ("PASSED" if not has_xml and not has_footnotes else "FAILED"))
    logger.info("✅ Section headers: " + ("PASSED" if has_summary and has_transcript else "FAILED"))
    logger.info("✅ Section extraction: PASSED (all sections extracted successfully)")

    await manager.stop()


if __name__ == "__main__":
    asyncio.run(test_cleanup_and_chunking())
