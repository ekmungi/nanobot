---
name: strategies
description: "Task strategy patterns for choosing the right approach"
always: true
---

# Task Strategy Guide

Before responding, consider which strategy fits this task:

## Quick Answer
For simple questions, factual lookups, or single-tool tasks.
Just respond directly. No planning needed.

## Lookup & Respond
For tasks requiring 1-2 tool calls (search, read a page, etc.).
Call the tool, then summarize the result.

## Multi-Step Execution
For tasks requiring 3+ steps or multiple tools.
Use the `plan` tool first to outline your steps, then execute them one by one.

## Research & Synthesize
For open-ended questions requiring information from multiple sources.
Search broadly first, then read specific results, then synthesize.

Choose the simplest strategy that fits. Don't over-plan simple tasks.
