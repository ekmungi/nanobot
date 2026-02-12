# Nanobot Project Instructions

This file contains project-specific instructions for Claude Code when working on the nanobot codebase.

## Project Organization

### Directory Structure

```
nanobot/
├── docs/                    # All documentation files
│   ├── YYYYMMDD_*.md       # Dated documentation (solutions, guides)
│   └── *.md                # General documentation (COMMUNICATION.md, etc.)
├── planning/               # Planning documents
│   └── YYYYMMDD_plan_*.md # Dated planning files
├── issues/                 # Issue tracking and investigations
│   └── YYYYMMDD_*/        # Issue-specific folders (YYYYMMDD_issue_name/)
│       ├── README.md       # Issue summary and index
│       └── YYYYMMDD_*.md  # Issue-related files
├── tests/                  # All test files
│   └── test_*.py          # Test modules
├── nanobot/               # Source code
│   ├── agent/            # Agent loop, tools, context
│   ├── channels/         # Communication channels
│   ├── cli/              # CLI interface
│   ├── config/           # Configuration loading
│   ├── mcp/              # MCP integration
│   ├── providers/        # LLM providers
│   ├── session/          # Session management
│   └── skills/           # Agent skills
└── README.md             # Main project README

```

### File Naming Conventions

1. **Documentation files**: `YYYYMMDD_descriptive_name.md`
   - Example: `20260212_notion_extraction_solution.md`

2. **Planning files**: `YYYYMMDD_plan_descriptive_name.md`
   - Example: `20260212_plan_mcp_integration.md`

3. **Issue folders**: `YYYYMMDD_issue_name/`
   - Example: `issues/20260212_notion_extraction/`
   - Must contain `README.md` with issue summary
   - All files inside use `YYYYMMDD_*.md` format

4. **Test files**: `test_*.py`
   - Must be in `tests/` folder
   - Example: `tests/test_mcp_notion.py`

### Organization Rules

1. **No files in project root** except:
   - `README.md` (main project README)
   - `CLAUDE.md` (this file)
   - `LICENSE`
   - Configuration files (`pyproject.toml`, `.gitignore`, etc.)
   - Build/deployment files (`Dockerfile`, etc.)
   - Images (`*.png`, `*.svg` for README)

2. **All documentation → `docs/`**
   - Guides, solutions, analyses
   - Date-prefix files that are time-specific

3. **All planning → `planning/`**
   - Project plans, architectural decisions
   - Always use date prefix

4. **All issues → `issues/YYYYMMDD_*/`**
   - Each issue gets own dated folder
   - Must include `README.md` index
   - All files inside are date-prefixed

5. **All tests → `tests/`**
   - Never in root or other directories
   - Follow pytest conventions

6. **No debug files**
   - Never commit `_debug_*.txt` or similar
   - Use proper logging instead

### When Creating New Files

**Before creating any file, ask:**
1. Is this documentation? → `docs/YYYYMMDD_name.md`
2. Is this a plan? → `planning/YYYYMMDD_plan_name.md`
3. Is this for an issue? → `issues/YYYYMMDD_issue_name/YYYYMMDD_file.md`
4. Is this a test? → `tests/test_name.py`
5. Is this source code? → Appropriate `nanobot/` subdirectory

**Never create:**
- Files in project root (except allowed list above)
- Files without date prefix (when applicable)
- Debug/temp files that should be gitignored

### Cleanup Procedure

When cleaning up the codebase:

1. **Find stale files**:
   ```bash
   # Root level (should be minimal)
   ls -la | grep "^-"

   # Debug files
   find . -name "_debug_*" -o -name "*.tmp"

   # Test files outside tests/
   find . -path ./tests -prune -o -name "test_*.py" -print
   ```

2. **Move to correct location**:
   - Documentation → `docs/`
   - Planning → `planning/`
   - Tests → `tests/`
   - Issues → `issues/YYYYMMDD_*/`

3. **Rename with date prefix**:
   - Use `YYYYMMDD_` prefix for dated files
   - Format: `20260212_descriptive_name.md`

4. **Remove stale files**:
   - Debug outputs
   - Temporary files
   - Duplicate/obsolete docs

## Code Organization

### MCP Integration

- **Wrappers**: `nanobot/mcp/wrappers/`
  - Semantic tool wrappers (hide raw MCP tool names)
  - Each server gets its own file: `wrappers/notion.py`, `wrappers/github.py`
  - Auto-detected via `wrappers/__init__.py` registry

- **Bridge**: `nanobot/mcp/bridge.py`
  - Raw MCP tool passthrough (fallback when no wrappers exist)
  - Schema simplification for large tool sets

- **Client**: `nanobot/mcp/client.py`
  - Connection manager, one task per server
  - Context managers must enter/exit in same task

### Testing

- **Location**: All tests in `tests/` folder
- **Running**: `uv run python tests/test_file.py` (no pytest installed)
- **Naming**: `test_*.py` for test modules
- **Coverage**: Test both success and failure paths

### Configuration

- **User config**: `~/.nanobot/config.json`
- **Schema**: `nanobot/config/schema.py` (Pydantic models)
- **Loader**: `nanobot/config/loader.py` (camelCase→snake_case conversion)
- **Gotcha**: Use `_PRESERVE_VALUE_KEYS` for env vars

## Common Tasks

### Adding a New MCP Server Wrapper

1. Create `nanobot/mcp/wrappers/server_name.py`
2. Implement `Tool` subclasses for semantic wrappers
3. Add `get_tools(manager) -> list[Tool]` function
4. Register in `nanobot/mcp/wrappers/__init__.py`
5. Test with `tests/test_mcp_server_name.py`
6. Document in `docs/YYYYMMDD_mcp_server_name.md`

### Creating a Planning Document

1. Create `planning/YYYYMMDD_plan_feature_name.md`
2. Include: Context, Goals, Approach, Files to Change, Risks
3. Link from issue folder if applicable

### Documenting a Solution

1. Create `docs/YYYYMMDD_solution_name.md`
2. Include: Problem, Analysis, Solution, Testing, Files Changed
3. Update relevant issue folder `README.md`
4. Update project memory if significant

## Environment Notes

- **OS**: Windows (use `uv run python`, not bare `python`)
- **Package manager**: `uv` (modern Python package manager)
- **Virtual env**: `.venv/` (managed by uv)
- **Config location**: `~/.nanobot/`
- **Workspace**: `~/.nanobot/workspace/`

## Git Workflow

### Committing Changes

When asked to commit:
1. **Never commit unless explicitly asked**
2. Review changes: `git status`, `git diff`
3. Stage specific files: `git add file1 file2` (not `git add .`)
4. Write clear commit message
5. Include co-author: `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`

### Files to Never Commit

- Debug files (`_debug_*`, `*.tmp`)
- Test outputs in root
- Stale planning docs
- Personal notes
- API keys/tokens (check config files)

## Best Practices

1. **Read before writing**: Always read existing code before modifying
2. **Test changes**: Run tests after modifications
3. **Keep it simple**: Don't over-engineer
4. **Document decisions**: Create dated docs for significant changes
5. **Clean as you go**: Remove stale files, organize new ones
6. **Follow conventions**: Use existing patterns in codebase

## Specific to This Project

### Notion Integration

- Remote server is primary (`mcp.notion.com`)
- Local server is fallback (`@notionhq/notion-mcp-server`)
- Automatic pagination fallback implemented
- See `docs/20260212_notion_extraction_solution.md`

### Memory Management

- Auto memory at `~/.claude/projects/*/memory/`
- Keep `MEMORY.md` under 200 lines
- Break out detailed content into separate topic files

### Skills

- Location: `nanobot/skills/*/SKILL.md`
- Frontmatter controls loading (`always: true`)
- Keep concise for small context windows

---

**Last updated**: 2026-02-12
**Maintained by**: Claude Code agents working on this project
