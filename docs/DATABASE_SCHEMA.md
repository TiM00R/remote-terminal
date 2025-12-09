# Remote Terminal - Database Schema

Complete SQLite database schema documentation for Version 3.0.

## Overview

Remote Terminal uses SQLite for persistent storage of:
- Server machine identities (hardware fingerprints)
- Command execution history
- Conversation tracking
- Recipe automation templates
- Batch execution records

**Database Location:** `data/remote_terminal.db`

---

## Tables

### servers

Stores unique machine identities and connection information.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `machine_id` | TEXT | PRIMARY KEY | Unique machine identifier from /etc/machine-id |
| `hostname` | TEXT | | Discovered hostname from remote server |
| `host` | TEXT | NOT NULL | Current IP address or hostname |
| `user` | TEXT | NOT NULL | SSH username |
| `port` | INTEGER | DEFAULT 22 | SSH port |
| `description` | TEXT | | Optional description |
| `tags` | TEXT | | Comma-separated tags for organization |
| `first_seen` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | First connection time |
| `last_seen` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Most recent connection time |
| `connection_count` | INTEGER | DEFAULT 0 | Total number of connections |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Indexes:**
- `idx_servers_connection` on (host, user, port)

**Key Notes:**
- `machine_id` is read from `/etc/machine-id` on the remote server
- Ensures commands are tracked per physical machine even if IP changes
- Connection details (host, user, port) are updated on each connection
- Tags enable organization: "production", "development", "backup", etc.

---

### conversations

Groups related commands by goal with tracking and rollback support.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique conversation ID |
| `machine_id` | TEXT | NOT NULL, FK servers(machine_id) | Machine where conversation occurs |
| `goal_summary` | TEXT | NOT NULL | Brief description of goal |
| `status` | TEXT | DEFAULT 'in_progress' | Current status |
| `started_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When conversation started |
| `ended_at` | TIMESTAMP | | When conversation ended |
| `created_by` | TEXT | DEFAULT 'claude' | Who created (always 'claude') |
| `user_notes` | TEXT | | Optional notes about outcome |

**Status Values:**
- `in_progress` - Actively being worked on
- `paused` - Temporarily suspended (can resume)
- `success` - Goal achieved
- `failed` - Goal not achieved
- `rolled_back` - Commands were undone

**Indexes:**
- `idx_conversations_machine` on (machine_id, status)

**Key Notes:**
- One conversation per goal (e.g., "Install nginx", "Debug WiFi")
- Commands can optionally belong to conversations
- Supports pause/resume for long-running tasks
- Source for recipe generation

---

### commands

Complete audit trail of all command executions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique command ID |
| `machine_id` | TEXT | NOT NULL, FK servers(machine_id) | Machine where executed |
| `conversation_id` | INTEGER | FK conversations(id), NULLABLE | Optional conversation link |
| `sequence_num` | INTEGER | NULLABLE | Sequence within conversation |
| `command_text` | TEXT | NOT NULL | The command executed |
| `result_output` | TEXT | | Command output |
| `status` | TEXT | DEFAULT 'executed' | Execution status |
| `exit_code` | INTEGER | | Command exit code |
| `has_errors` | BOOLEAN | DEFAULT 0 | Whether output contains errors |
| `error_context` | TEXT | | Extracted error details |
| `line_count` | INTEGER | DEFAULT 0 | Number of output lines |
| `backup_file_path` | TEXT | | Path to backup file if created |
| `backup_created_at` | TIMESTAMP | | When backup was created |
| `backup_size_bytes` | INTEGER | | Size of backup file |
| `executed_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When command executed |
| `undone_at` | TIMESTAMP | | When command was undone (rollback) |
| `batch_execution_id` | INTEGER | FK batch_executions(id), NULLABLE | Batch execution link |

**Status Values:**
- `executed` - Command completed
- `cancelled` - User interrupted (Ctrl+C)
- `timeout` - Exceeded timeout
- `undone` - Reversed during rollback

**Indexes:**
- `idx_commands_conversation` on (conversation_id, sequence_num)
- `idx_commands_machine` on (machine_id, executed_at)

**Key Notes:**
- ALL commands tracked, conversation link is optional
- `sequence_num` only set if `conversation_id` provided
- Error detection happens automatically via output analysis
- Backup files tracked for potential rollback operations
- Batch commands link to `batch_executions` table

---

### recipes

Reusable automation templates created from successful conversations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique recipe ID |
| `name` | TEXT | UNIQUE NOT NULL | Recipe name (e.g., 'wifi_diagnostics') |
| `description` | TEXT | NOT NULL | What the recipe does |
| `command_sequence` | TEXT | NOT NULL | JSON array of commands |
| `prerequisites` | TEXT | | System requirements |
| `success_criteria` | TEXT | | How to verify success |
| `source_conversation_id` | INTEGER | FK conversations(id), NULLABLE | Source conversation |
| `times_used` | INTEGER | DEFAULT 0 | Usage counter |
| `last_used_at` | TIMESTAMP | | Last execution time |
| `created_by` | TEXT | DEFAULT 'claude' | Who created (always 'claude') |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Command Sequence Format (JSON):**
```json
[
    {
        "command": "ip link show",
        "description": "Check network interfaces"
    },
    {
        "command": "ip route show",
        "description": "Check routing table"
    }
]
```

**Key Notes:**
- Created from successful conversations
- Can be executed on any compatible server
- Usage statistics tracked automatically
- Prerequisites and success criteria help determine compatibility

---

### batch_executions

Tracks batch script execution sessions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique batch execution ID |
| `machine_id` | TEXT | NOT NULL, FK servers(machine_id) | Machine where executed |
| `conversation_id` | INTEGER | FK conversations(id), NULLABLE | Optional conversation link |
| `script_name` | TEXT | NOT NULL | Name of the batch script |
| `total_steps` | INTEGER | NOT NULL | Total steps in script |
| `completed_steps` | INTEGER | DEFAULT 0 | Steps completed so far |
| `status` | TEXT | DEFAULT 'running' | Execution status |
| `started_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When execution started |
| `completed_at` | TIMESTAMP | | When execution completed |
| `duration_seconds` | REAL | | Total execution time |

**Status Values:**
- `pending` - Queued but not started
- `running` - Currently executing
- `completed` - Finished successfully
- `failed` - Execution failed
- `timeout` - Exceeded timeout

**Key Notes:**
- Progress tracking via `completed_steps` / `total_steps`
- Individual commands link back via `commands.batch_execution_id`
- Duration calculated automatically
- Can be tracked in conversation for context

---

### batch_scripts

Library of reusable batch scripts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique script ID |
| `name` | TEXT | UNIQUE NOT NULL | Script name/filename |
| `description` | TEXT | | What the script does |
| `script_content` | TEXT | NOT NULL | Complete bash script |
| `content_hash` | TEXT | | SHA256 hash for deduplication |
| `created_by` | TEXT | DEFAULT 'claude' | Who created (always 'claude') |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `times_used` | INTEGER | DEFAULT 0 | Usage counter |
| `last_used_at` | TIMESTAMP | | Last execution time |

**Indexes:**
- `idx_batch_scripts_hash` on (content_hash)

**Key Notes:**
- Stores complete bash script content
- Hash enables deduplication (same script = same hash)
- Usage statistics for popular scripts
- Scripts can be updated (name stays same, content_hash changes)

---

## Relationships

```
servers (machine_id)
    ├─→ conversations (machine_id)
    │       ├─→ commands (conversation_id)
    │       ├─→ batch_executions (conversation_id)
    │       └─→ recipes (source_conversation_id)
    ├─→ commands (machine_id)
    └─→ batch_executions (machine_id)
            └─→ commands (batch_execution_id)

batch_scripts
    (standalone library, linked by name during execution)
```

### Key Relationships

1. **servers → conversations** (1:many)
   - One machine can have many conversations
   - Each conversation belongs to one machine

2. **servers → commands** (1:many)
   - All commands tracked per machine
   - Commands can exist without conversation

3. **conversations → commands** (1:many, optional)
   - Conversation can group multiple commands
   - Commands can be standalone (no conversation)

4. **conversations → recipes** (1:1, optional)
   - Successful conversation can become recipe
   - Recipe preserves source conversation ID

5. **batch_executions → commands** (1:many)
   - Batch execution spawns multiple commands
   - Commands link back to batch execution

6. **servers → batch_executions** (1:many)
   - Machine executes batch scripts
   - Execution tracked per machine

---

## Database Operations

### Common Queries

**Get machine's recent commands:**
```sql
SELECT * FROM commands 
WHERE machine_id = ? 
ORDER BY executed_at DESC 
LIMIT 50
```

**Get active conversation for machine:**
```sql
SELECT * FROM conversations 
WHERE machine_id = ? AND status = 'in_progress'
ORDER BY started_at DESC 
LIMIT 1
```

**Get conversation's command sequence:**
```sql
SELECT * FROM commands 
WHERE conversation_id = ? 
ORDER BY sequence_num ASC
```

**Get paused conversations for machine:**
```sql
SELECT * FROM conversations 
WHERE machine_id = ? AND status = 'paused'
ORDER BY started_at DESC
```

**List available recipes:**
```sql
SELECT id, name, description, times_used 
FROM recipes 
ORDER BY created_at DESC
```

**Get batch execution progress:**
```sql
SELECT total_steps, completed_steps, 
       CAST(completed_steps AS FLOAT) / total_steps * 100 AS progress_pct
FROM batch_executions 
WHERE id = ?
```

---

## Database Management

### Backup

```powershell
# Manual backup
Copy-Item "D:\Projects\remote_terminal\data\remote_terminal.db" `
          "D:\Projects\remote_terminal\data\backups\remote_terminal_$(Get-Date -Format 'yyyyMMdd_HHmmss').db"
```

### Vacuum (Optimize)

```powershell
python -c "import sqlite3; conn = sqlite3.connect('data/remote_terminal.db'); conn.execute('VACUUM'); conn.close(); print('Vacuumed')"
```

### Integrity Check

```powershell
python -c "import sqlite3; conn = sqlite3.connect('data/remote_terminal.db'); result = conn.execute('PRAGMA integrity_check').fetchone(); print(result[0])"
```

Expected output: `ok`

### View Database

Use the included utility:
```powershell
python view_db.py
```

This shows:
- Server count and details
- Conversation statistics
- Command counts by status
- Recipe library
- Batch execution history

---

## Migration Notes

### From PostgreSQL (Version 2.0)

Version 3.0 switched from PostgreSQL to SQLite with these changes:

**Schema changes:**
- `machines` → `servers` (renamed table)
- `machine_id` remains primary identifier
- Added `content_hash` to batch_scripts for deduplication
- All SERIAL → AUTOINCREMENT
- TIMESTAMPTZ → TIMESTAMP

**Removed dependencies:**
- No Docker required
- No PostgreSQL installation
- Self-contained database file

**Benefits:**
- Simpler deployment (single .db file)
- No external database server
- Easier backup (copy one file)
- Portable across machines

---

## Configuration

Database settings in `config.yaml`:

```yaml
database:
  path: data/remote_terminal.db
  backup:
    enabled: true
    interval_days: 7
  maintenance:
    vacuum_on_startup: true
    optimize_interval_days: 30
```

---

## Performance Considerations

### Indexes

All critical query paths are indexed:
- Server lookups by connection details
- Command queries by machine and timestamp
- Conversation queries by machine and status
- Batch script lookups by content hash

### Connection Pooling

SQLite uses `check_same_thread=False` for concurrent access.  
**Important:** Only one MCP server instance should run per database.

### Database Size

Typical growth:
- 1 KB per command (with output)
- 2 KB per conversation
- 5 KB per recipe
- 10 KB per batch script

**Example:** 10,000 commands = ~10 MB

### Maintenance

Auto-vacuum runs on startup (configurable).  
Manual optimization recommended monthly for active use.

---

**Version:** 3.0 (SQLite-based)  
**Last Updated:** December 2024  
**Schema Version:** 1.0
