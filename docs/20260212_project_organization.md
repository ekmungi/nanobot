# Project Organization Cleanup - 2026-02-12

## Summary

Reorganized the nanobot project structure to follow consistent conventions with proper directory hierarchy and file naming.

## Changes Made

### 1. Directory Structure Created

```
nanobot/
├── docs/                    # All documentation files ✅
├── planning/               # Planning documents ✅
├── issues/                 # Issue tracking folders ✅
├── tests/                  # All test files ✅
├── nanobot/               # Source code (existing)
├── bridge/                # WhatsApp bridge (existing)
├── case/                  # Demo GIFs (existing)
└── workspace/             # Agent workspace templates (existing)
```

### 2. Files Moved and Renamed

**Documentation (`docs/`)**:
- `COMMUNICATION.md` → `docs/COMMUNICATION.md`
- `README_ANALYSIS.md` → `docs/README_ANALYSIS.md`
- `SECURITY.md` → `docs/SECURITY.md`
- `SOLUTION_SUMMARY.md` → `docs/20260212_notion_extraction_solution.md` ✨

**Planning (`planning/`)**:
- `PROJECT_PLAN.md` → `planning/20260212_project_plan.md` ✨

**Issues (`issues/20260212_notion_extraction/`)**:
- `Issues_tracker/notion_extraction_issue/*` → `issues/20260212_notion_extraction/`
- Renamed all files with `20260212_` prefix ✨
- Created `README.md` index for the issue

### 3. Files Removed

**Stale/Debug files**:
- `_debug_page.txt` ❌
- `_debug_search.txt` ❌
- `=1.0.0` ❌
- `=3.9.0` ❌
- `nul` ❌
- `core_agent_lines.sh` ❌

### 4. Issue Files Reorganized

**Inside `issues/20260212_notion_extraction/`**:
```
EXTRACTION_ANALYSIS.md          → 20260212_extraction_analysis.md
EXTRACTION_COMPARISON.txt       → 20260212_extraction_comparison.txt
NEXT_STEPS.md                   → 20260212_next_steps.md
potential_notion_extraction_solution.md → 20260212_proposed_solution.md
QUICK_REFERENCE.txt             → 20260212_quick_reference.txt
START_HERE.txt                  → 20260212_start_here.txt
TEST_RESULTS_SUMMARY.md         → 20260212_test_results.md
                                → README.md (new index)
```

### 5. Project Guidelines Created

**New file**: `CLAUDE.md`

Contains comprehensive project organization instructions including:
- Directory structure and purpose
- File naming conventions (`YYYYMMDD_*.md`)
- Organization rules
- Common tasks and workflows
- Best practices
- Project-specific notes

## File Naming Convention

### Format: `YYYYMMDD_descriptive_name.md`

**Examples**:
- ✅ `20260212_notion_extraction_solution.md`
- ✅ `20260212_plan_feature_name.md`
- ✅ `20260212_extraction_analysis.md`
- ❌ `SOLUTION.md` (no date)
- ❌ `2026-02-12_solution.md` (wrong format)

### When to Use Date Prefix

**Use date prefix**:
- Solutions and implementation docs
- Planning documents
- Issue-related files
- Time-specific analyses

**Don't use date prefix**:
- General project docs (README.md, SECURITY.md)
- Architecture docs (ARCHITECTURE.md)
- Ongoing documentation (COMMUNICATION.md)

## Current State

### Root Directory (Minimal)

Allowed files in root:
- `README.md` - Main project README
- `CLAUDE.md` - Project instructions for AI agents
- `LICENSE` - License file
- `Dockerfile` - Container build
- `pyproject.toml` - Python project config
- `uv.lock` - Dependency lock file
- `.gitignore` - Git ignore rules
- `*.png`, `*.svg` - Images for README

Directories in root:
- `nanobot/` - Source code
- `tests/` - Test files
- `docs/` - Documentation
- `planning/` - Planning docs
- `issues/` - Issue tracking
- `bridge/` - WhatsApp bridge
- `case/` - Demo GIFs
- `workspace/` - Agent templates

### Statistics

- **Tests**: 4 test files in `tests/`
- **Docs**: 7 documentation files in `docs/`
- **Issues**: 1 issue folder with 8 files
- **Planning**: 1 planning document

## Benefits

1. **Consistency**: All files follow same naming convention
2. **Findability**: Related files grouped in logical directories
3. **Traceability**: Date prefixes show chronological order
4. **Maintainability**: Clear structure makes it easy to add new content
5. **Automation**: Conventions enable scripted organization checks

## Future Guidelines

### Adding New Files

**Before creating**:
1. Determine category (docs/planning/issue/test)
2. Apply appropriate naming convention
3. Place in correct directory
4. Update relevant index files

**For issues**:
1. Create `issues/YYYYMMDD_issue_name/` folder
2. Add `README.md` with summary
3. Add issue files with `YYYYMMDD_` prefix
4. Link to solution in `docs/` when resolved

**For planning**:
1. Create `planning/YYYYMMDD_plan_name.md`
2. Include context, goals, approach, risks
3. Link from related issue if applicable

### Cleanup Process

**Regular cleanup**:
```bash
# Find files in wrong location
find . -maxdepth 1 -name "*.md" ! -name "README.md" ! -name "CLAUDE.md"

# Find test files outside tests/
find . -path ./tests -prune -o -name "test_*.py" -print

# Find debug files
find . -name "_debug_*" -o -name "*.tmp"
```

## Related Files

- `CLAUDE.md` - Complete project organization guide
- `issues/20260212_notion_extraction/README.md` - Example issue index
- `docs/20260212_notion_extraction_solution.md` - Example solution doc

## Next Steps

1. ✅ Structure created
2. ✅ Files organized
3. ✅ Guidelines documented
4. ⏭️ Apply to future work automatically

---

**Completed**: 2026-02-12
**Files reorganized**: 20+
**Stale files removed**: 6
**New guidelines**: CLAUDE.md created
