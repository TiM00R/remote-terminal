# Release Notes - Version 3.1 (December 16, 2024)

## Overview

Added comprehensive batch script management system with 5 new MCP tools and standalone UI enhancements.

---

## NEW FEATURES

### 1. Batch Script Management Tools (5 new tools)

**`list_batch_scripts`**
- Browse saved scripts with filtering (most_used, recently_used, newest, oldest)
- Search by name/description
- Pagination support (up to 200 results)
- Shows usage statistics and creation dates

**`get_batch_script`**
- View complete script details and content by ID
- Returns usage statistics and content hash
- For inspection before execution or editing

**`save_batch_script`**
- Save batch scripts to database for reuse
- **Edit mode:** Load existing script by ID for modification
- **Automatic deduplication:** SHA256 content hash prevents duplicates
- Tracks usage statistics (times_used, last_used_at)

**`execute_batch_script_by_id`**
- Execute saved script by ID
- Same features as execute_script_content
- Automatically increments usage counter
- Links to conversation tracking if specified

**`delete_batch_script`**
- **Two-step confirmation:** First call shows details, second call deletes
- Permanent hard delete (not recoverable)
- Execution history preserved but script content removed

### 2. Tool Renaming (for clarity)

**Old names → New names:**
- `create_diagnostic_script` → `build_script_from_commands`
- `execute_batch_script` → `execute_script_content`

**Reason:** Clarify that one builds from command list (without executing), the other executes direct script content.

### 3. Standalone UI Enhancements

**Batch Scripts Tab Features:**
- **Script dropdown selectors** (`script_select` field type) - like recipe_select, command_select
- **Auto-population:** Selecting script loads both content AND description
- **Bash syntax highlighting:** VS Code-style colors
  - Green comments (#)
  - Orange strings
  - Purple keywords (if, then, else, for, while, etc.)
  - Cyan variables ($VAR)
  - Teal built-in commands (ls, cd, grep, etc.)
- **Numerical sorting:** Scripts sorted 1, 2, 3... (not 1, 11, 12...)
- **Real-time loading:** Scripts loaded fresh on tab switch

**UI Components:**
- ContentEditable `<pre>` element with live syntax highlighting
- New CSS file: `control-styles.css` for bash-editor styling
- Dark theme with VS Code color scheme
- Script content parsing from markdown code blocks

---

## KEY FEATURES

### Automatic Deduplication
- Scripts deduplicated via SHA256 content hash
- Same script content = same database entry  
- Usage statistics tracked per unique script
- Prevents duplicate storage

### Usage Statistics
- `times_used`: Execution counter
- `last_used_at`: Most recent execution timestamp
- Helps identify popular/useful scripts
- Displayed in script lists

### Edit Mode
- Load existing script by ID in save_batch_script
- Modify content in UI with syntax highlighting
- Save creates new version if content changed
- Preserves script library organization

### Database Integration
- Scripts stored in `batch_scripts` table
- Execution history in `batch_executions` table
- Full command tracking in `commands` table
- Machine-specific tracking via machine_id

---

## TYPICAL WORKFLOWS

### Create and Reuse
```
1. User: "Run docker diagnostics"
   Claude: [Creates batch script, executes, auto-saves to database]

2. User: "List my batch scripts"
   Claude: [Shows all saved scripts with usage stats]

3. User: "Execute script 5"
   Claude: [Loads from database, runs, increments usage counter]
```

### Edit Existing Script
```
1. User: "Load script 5 for editing" (in standalone UI)
   [Script content and description populate fields]

2. User: [Modifies script content in syntax-highlighted editor]

3. User: "Save updated script"
   Claude: [New version saved if content changed, deduplication applied]
```

### Browse and Clean Up
```
1. User: "Show my most used batch scripts"
   Claude: [Lists scripts sorted by times_used]

2. User: "Delete old script 3"
   Claude: [Shows details, asks for confirmation]

3. User: "Confirm deletion"
   Claude: [Permanently removes script, execution history preserved]
```

---

## TECHNICAL DETAILS

### Database Schema Changes

**batch_scripts table:**
- Added `description` column (moved from batch_executions)
- Column: `script_content` (stores complete bash script)
- Column: `content_hash` (SHA256 for deduplication)
- Column: `times_used` (usage counter)
- Column: `last_used_at` (timestamp)

**Why move description:**
- Description logically belongs to the script, not the execution event
- Enables searching scripts by description
- Better data organization

### UI Implementation

**New Field Type: `script_select`**
```javascript
// Dropdown populated with scripts from database
// Format: "ID - Description (truncated to 60 chars)"
// Auto-sorted numerically by ID
```

**Bash Syntax Highlighting:**
```javascript
function highlightBash(code) {
    // Escapes HTML entities first
    // Applies color spans for: comments, strings, keywords, 
    // variables, commands, numbers
    // Returns highlighted HTML
}
```

**Script Loading:**
```javascript
// On script_id dropdown change:
// 1. Fetch script via get_batch_script tool
// 2. Parse markdown-wrapped content
// 3. Populate content field (with highlighting)
// 4. Populate description field
```

---

## FILES MODIFIED

### Backend
- `src/tools/tools_batch.py` - Added 5 new tool implementations
- `standalone/static/tool-schemas/batch.json` - Added 5 new tool schemas, renamed 2 tools

### Frontend
- `standalone/static/js/control-main.js` - Added loadBatchScripts(), getBatchScripts()
- `standalone/static/js/control-forms.js` - Added createScriptSelectField(), highlightBash(), cursor helpers
- `standalone/static/css/control-styles.css` - Created new file with bash-editor styles
- `standalone/mcp_control.html` - Added link to control-styles.css

### Documentation
- `docs/FEATURE_REFERENCE.md` - Updated with 5 new tools, renamed tools, new features
- `docs/RELEASE_NOTES_v3.1.md` - This file
- `README.md` - Updated version history and key features

---

## BREAKING CHANGES

**Tool Renaming:**
- Old: `create_diagnostic_script` → New: `build_script_from_commands`
- Old: `execute_batch_script` → New: `execute_script_content`

**Impact:** Existing code/prompts using old names will need updates.

**Migration:** Update any references to use new names.

---

## USAGE STATISTICS

**Before:**
- Batch scripts executed but not saved
- No reusability
- No usage tracking

**After:**
- Scripts automatically saved with deduplication
- Full reusability via script_id
- Usage statistics tracked (times_used, last_used_at)
- Edit mode for modifications
- Searchable script library

---

## NEXT STEPS

Potential future enhancements:
- Script versioning (keep history of modifications)
- Script sharing/export
- Script categories/tags
- Script templates
- Batch script diff viewer
- Import scripts from files

---

**Version:** 3.1  
**Release Date:** December 16, 2024  
**Author:** Tim Moor
