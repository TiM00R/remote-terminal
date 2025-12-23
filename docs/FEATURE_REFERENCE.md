# Remote Terminal - Feature Reference

Quick reference for all MCP tools and capabilities.

---

## Table of Contents

1. [MCP Tools Available to Claude](#mcp-tools-available-to-claude)
   - [Server Management Tools](#server-management-tools)
   - [Command Execution Tools](#command-execution-tools)
   - [Batch Script Execution Tools](#batch-script-execution-tools)
   - [Batch Script Management Tools](#batch-script-management-tools)
   - [File Transfer Tools (SFTP)](#file-transfer-tools-sftp)
   - [Conversation Management Tools](#conversation-management-tools)
   - [Recipe Management Tools](#recipe-management-tools)
2. [Batch Script Management Features](#batch-script-management-features)
3. [Usage Patterns](#usage-patterns)
4. [Output Filtering Rules](#output-filtering-rules)
5. [Database Tables](#database-tables)
6. [Configuration Options](#configuration-options)

---

## MCP Tools Available to Claude

### Server Management Tools

#### `list_servers`
List all configured servers from hosts.yaml with status markers

**No parameters required**

**Returns:** List of servers with:
- Server names, hosts, ports, users
- Descriptions and tags
- **Status markers:**
  - `[CURRENT]` - Currently connected server
  - `[DEFAULT]` - Default server (auto-connects when no server specified)

**Examples:**
```
Claude, show me all my servers
Which server is set as default?
```
---

#### `set_default_server`
Set a server as default for automatic connections

**Parameters:**
- `identifier` (required): Server name or host

**Returns:** Confirmation message

**What it does:**
- Marks the server with `[DEFAULT]` in `list_servers` output
- When executing commands without an active connection, Claude automatically connects to the default server
- Users can see which server is default by running `list_servers`

**Examples:**
```
Set production-server as my default
Make my development server the default
```
---


#### `select_server`
Connect to a specific server by name, host, or tag

**Parameters:**
- `identifier` (required): Server name, IP address, or tag
- `force_identity_check` (optional): Force re-read machine_id from server (default: false)

**Returns:** Connection status, server info, open conversations (if any)

**Examples:**
```
Connect to production-server
Switch to 192.168.1.100
Connect to the server tagged 'development'
Connect to my-server and verify its identity
```

**Important:** If open conversations exist on the selected server, Claude must ask user to choose:
- Resume specific conversation
- Start new conversation
- Run without conversation mode

---

#### `get_current_server`
Get information about currently connected server

**No parameters required**

**Returns:** Current server name, host, user, connection status

**Example:**
```
Which server am I connected to?
```
---


#### `add_server`
Add a new server to configuration

**Parameters:**
- `name` (required): Friendly server name
- `host` (required): IP address or hostname
- `user` (required): SSH username
- `password` (required): SSH password
- `port` (optional): SSH port (default: 22)
- `description` (optional): Server description
- `tags` (optional): Comma-separated tags

**Returns:** Confirmation

**Example:**
```
Add a new server named 'backup' at 192.168.1.102 with user 'admin' and password 'pass123'
```

---

#### `remove_server`
Remove a server from configuration

**Parameters:**
- `identifier` (required): Server name or host to remove

**Returns:** Confirmation

**Example:**
```
Remove the server named 'old-server'
```

---

#### `update_server`
Update existing server configuration

**Parameters:**
- `identifier` (required): Current server name or host
- `name` (optional): New name
- `host` (optional): New host
- `user` (optional): New username
- `password` (optional): New password
- `port` (optional): New port
- `description` (optional): New description
- `tags` (optional): New tags

**Returns:** Confirmation with updated values

**Example:**
```
Update production-server to use port 2222
```

---

### Command Execution Tools

#### `execute_command`
Execute a command on the remote server with smart filtering

**Parameters:**
- `command` (required): The bash command to execute
- `timeout` (optional): Maximum seconds to wait (default: 10, max: 3600)
- `output_mode` (optional): auto, full, preview, summary, minimal, raw (default: auto)
- `conversation_id` (optional): Associate with conversation for tracking

**Returns:** 
- `status`: completed, cancelled, timeout_still_running, backgrounded
- `output`: Filtered or full based on output_mode
- `command_id`: Unique identifier for checking status
- `buffer_info`: Information about full output availability

**Output Modes:**
- `auto`: Smart decision (default)
- `full`: Complete output
- `preview`: First 10 + last 10 lines
- `summary`: Metadata only
- `minimal`: Status + buffer_info
- `raw`: Unfiltered complete output

**Examples:**
```
Run 'df -h' on my server
Check disk space (this might take a while)
List all files in /var/log and show me everything
```

---

#### `check_command_status`
Check status of a long-running command

**Parameters:**
- `command_id` (required): Command ID from execute_command
- `output_mode` (optional): How much output to return (default: auto)

**Returns:** Current status, output preview, completion info

**Example:**
```
What's the status of command abc123?
```

---

#### `get_command_output`
Get full unfiltered output of a completed command

**Parameters:**
- `command_id` (required): Command ID
- `raw` (optional): True for completely unfiltered (default: false)

**Returns:** Complete output buffer

**Example:**
```
Show me the full output from the last command
```

---

#### `cancel_command`
Send Ctrl+C to interrupt a running command

**Parameters:**
- `command_id` (required): Command ID to cancel

**Returns:** Cancellation status

**Example:**
```
Cancel the current command
Stop command abc123
```

---

#### `list_commands`
List tracked commands with status

**Parameters:**
- `status_filter` (optional): 'running', 'completed', or 'killed'

**Returns:** List of commands with IDs, status, timestamps

**Example:**
```
Show me all running commands
List recent completed commands
```

---

#### `get_terminal_status`
Check connection and terminal status

**No parameters required**

**Returns:** Connection status, server info, SSH session state

**Example:**
```
Check the connection status
Is the terminal connected?
```

---

### Batch Script Execution Tools

#### `execute_script_content`
Execute multi-command bash script directly (provide complete script content)

**Parameters:**
- `script_content` (required): Complete bash script with step markers
- `description` (required): What the script does
- `timeout` (optional): Max execution time (default: 300 seconds)
- `conversation_id` (optional): Link to conversation
- `output_mode` (optional): summary or full (default: summary)

**Returns:**
- `status`: completed, timeout, error
- `execution_time`: Duration
- `steps_completed`: "N/Total"
- `error_detected`: Boolean
- `error_summary`: Error details if any
- `output_preview`: First/last lines
- `local_log_file`: Path to full log on local machine

**Script Format:**
```bash
#!/bin/bash
set -e
set -o pipefail

echo "=== [STEP 1/3] Description ==="
command_here
echo "[STEP_1_COMPLETE]"

echo "=== [STEP 2/3] Description ==="
another_command
echo "[STEP_2_COMPLETE]"

# More steps...

echo "[ALL_DIAGNOSTICS_COMPLETE]"
```

**Examples:**
```
Run complete network diagnostics
Check WiFi hardware and drivers
Investigate docker installation status
```

---

#### `build_script_from_commands`
Generate a batch script from command list (returns script text, does not execute)

**Parameters:**
- `commands` (required): List of {description, command} objects
- `description` (optional): Overall script description

**Returns:** Formatted script ready for execute_script_content

**Example:**
```python
commands = [
    {"description": "Check interfaces", "command": "ip link show"},
    {"description": "Check routing", "command": "ip route show"}
]
```

---

### Batch Script Management Tools

#### `list_batch_scripts`
Browse saved batch scripts from database

**Parameters:**
- `limit` (optional): Max results (default: 50, max: 200)
- `offset` (optional): Pagination offset (default: 0)
- `sort_by` (optional): most_used, recently_used, newest, oldest (default: recently_used)
- `search` (optional): Search in name/description

**Returns:** List of scripts with:
- ID, name, description
- Usage statistics (times_used, last_used_at)
- Creation date
- Content size

**Examples:**
```
Show me all saved batch scripts
List my most frequently used scripts
Search for scripts containing 'docker'
```

---

#### `get_batch_script`
View batch script details and content by ID

**Parameters:**
- `script_id` (required): Script ID from list_batch_scripts

**Returns:**
- Complete script details
- Full script content
- Usage statistics
- Content hash

**Example:**
```
Show me script 5
What's in the network inspection script?
```

---

#### `save_batch_script`
Save batch script to database for reuse (optional: load existing for editing)

**Parameters:**
- `script_id` (optional): Load existing script for editing
- `content` (required): Complete bash script content
- `description` (required): What this script does

**Returns:** 
- Script ID (new or reused via deduplication)
- Confirmation message
- Deduplication notice if script already exists

**Features:**
- Automatic deduplication via SHA256 content hash
- Edit mode: Specify script_id to load existing script for modification
- Tracks usage statistics

**Examples:**
```
Save this network inspection script
Load script 5 for editing and save with changes
```

---

#### `execute_batch_script_by_id`
Execute a saved batch script by ID

**Parameters:**
- `script_id` (required): Script ID from list_batch_scripts
- `timeout` (optional): Max execution time (default: 300 seconds)
- `output_mode` (optional): summary or full (default: summary)
- `conversation_id` (optional): Link to conversation

**Returns:** Same as execute_script_content

**Examples:**
```
Execute script 5
Run the docker diagnostics script
```

---

#### `delete_batch_script`
Delete batch script from database (requires confirmation)

**Parameters:**
- `script_id` (required): Script ID to delete
- `confirm` (optional): Confirmation flag (default: false)

**Returns:**
- First call: Shows script details and warning
- Second call (with confirm=true): Deletes and confirms

**Process:**
1. First call shows what will be deleted
2. Second call with confirm=true actually deletes

**Examples:**
```
Delete script 3
Confirm deletion of script 5
```

---

### File Transfer Tools (SFTP)

#### `upload_file`
Upload single file to remote server

**Parameters:**
- `local_path` (required): Absolute local path (e.g., C:\Users\WindowsUser\file.txt)
- `remote_path` (required): Absolute remote path (e.g., /home/linuxuser/file.txt)
- `overwrite` (optional): Replace existing (default: true)
- `preserve_timestamp` (optional): Copy modification time (default: true)
- `chmod` (optional): Set permissions in decimal (e.g., 493 for 0o755)

**Returns:** Upload status, file size, transfer time

**Example:**
```
Upload C:\config.json to /etc/app/config.json
```

---

#### `download_file`
Download single file from remote server

**Parameters:**
- `remote_path` (required): Absolute remote path
- `local_path` (required): Absolute local path
- `overwrite` (optional): Replace existing (default: true)
- `preserve_timestamp` (optional): Copy modification time (default: true)

**Returns:** Download status, file size, transfer time

**Example:**
```
Download /var/log/app.log to C:\Logs\app.log
```

---

#### `upload_directory`
Smart directory upload with automatic compression

**Parameters:**
- `local_path` (required): Local directory path
- `remote_path` (required): Remote directory path
- `recursive` (optional): Include subdirectories (default: true)
- `compression` (optional): auto, always, never (default: auto)
- `if_exists` (optional): merge, overwrite, skip, error (default: merge)
- `exclude_patterns` (optional): Glob patterns to exclude
- `preserve_timestamps` (optional): Copy modification times (default: true)
- `chmod_files` (optional): File permissions in decimal
- `chmod_dirs` (optional): Directory permissions in decimal
- `background` (optional): Auto-decide or force background mode

**Returns:** Transfer status, files transferred, time, compression used

**Examples:**
```
Upload D:\Projects\myapp to /home/linuxuser/myapp
Upload with compression always enabled
Upload but exclude node_modules and .git folders
```

---

#### `download_directory`
Smart directory download with automatic compression

**Parameters:** Same as upload_directory

**Returns:** Download status, files transferred, time, compression used

**Example:**
```
Download /home/linuxuser/myapp to D:\Projects\myapp
```

---

#### `list_remote_directory`
List contents of remote directory

**Parameters:**
- `remote_path` (required): Remote directory path
- `recursive` (optional): Traverse subdirectories (default: false)
- `show_hidden` (optional): Include hidden files (default: false)

**Returns:** List of files with sizes, permissions, timestamps

**Example:**
```
List files in /var/log
Show all files including hidden in /etc
```

---

#### `get_remote_file_info`
Get detailed information about remote file or directory

**Parameters:**
- `remote_path` (required): Remote file or directory path

**Returns:** Size, permissions, owner, timestamps, type

**Example:**
```
Get info about /etc/nginx/nginx.conf
```

---

### Conversation Management Tools

#### `start_conversation`
Begin tracking commands by goal

**Parameters:**
- `goal_summary` (required): Brief description of goal
- `server_identifier` (optional): Server to use (default: current)
- `force` (optional): Force new even if conversation in progress (default: false)

**Returns:** 
- `conversation_id`: ID to use with commands
- `machine_id`: Database ID of server
- Warning if conversation already in progress

**Example:**
```
Start a conversation to configure WiFi
```

---

#### `resume_conversation`
Resume a paused conversation

**Parameters:**
- `conversation_id` (required): Conversation ID to resume

**Returns:** Confirmation, goal summary

**Example:**
```
Resume conversation 5
Continue our WiFi configuration work
```

---

#### `end_conversation`
Mark conversation complete with status

**Parameters:**
- `conversation_id` (required): Conversation ID
- `status` (required): success, failed, or rolled_back
- `user_notes` (optional): Additional notes about outcome

**Returns:** Confirmation, final status

**Examples:**
```
End conversation - it worked!
End conversation 5 with status failed
```

---

#### `get_conversation_commands`
Get all commands from a conversation

**Parameters:**
- `conversation_id` (required): Conversation ID
- `reverse_order` (optional): Return in undo sequence (default: false)

**Returns:** Array of commands with:
- Command text
- Result output
- Error flags
- Backup file paths
- Status (executed or undone)

**Example:**
```
Show me all commands from conversation 5
```

---

#### `list_conversations`
List conversations with optional filters

**Parameters:**
- `server_identifier` (optional): Filter by server
- `status` (optional): in_progress, paused, success, failed, rolled_back
- `limit` (optional): Max results (default: 50)

**Returns:** List of conversations with goals, status, dates

**Examples:**
```
Show me all conversations
List successful conversations from last week
Show conversations on production-server
```

---

#### `update_command_status`
Mark command as undone (for rollback tracking)

**Parameters:**
- `command_id` (required): Command ID from get_conversation_commands
- `status` (required): Currently only 'undone' supported

**Returns:** Confirmation

**Example:**
Used internally during rollback operations

---

### Recipe Management Tools

#### `create_recipe`
Create reusable recipe from successful conversation

**Parameters:**
- `conversation_id` (required): Source conversation
- `name` (required): Short descriptive name (e.g., wifi_diagnostics)
- `description` (required): What the recipe does
- `prerequisites` (optional): System requirements
- `success_criteria` (optional): How to verify success

**Returns:**
- `recipe_id`: ID for later use
- `name`: Recipe name
- `command_count`: Number of commands

**Example:**
```
Create a recipe from conversation 5 named 'wifi_diagnostics'
```

---

#### `create_recipe_from_commands`
Create recipe manually from command list (no conversation required)

**Parameters:**
- `name` (required): Unique recipe name
- `description` (required): What the recipe does
- `commands` (required): Array of command objects with:
  - `sequence`: Step number
  - `command`: Shell command OR
  - `type`: "mcp_tool" (for MCP tool calls)
  - `tool`: Tool name (if type=mcp_tool)
  - `params`: Tool parameters (if type=mcp_tool)
  - `description`: What this step does
- `prerequisites` (optional): System requirements
- `success_criteria` (optional): How to verify success

**Returns:**
- `recipe_id`: New recipe ID
- `name`: Recipe name
- `command_count`: Number of commands

**Example:**
```
Create a recipe from scratch with these commands: check disk, check memory, check CPU
```

**Use Cases:**
- Build recipes from documentation
- Combine commands from multiple sources
- Create recipes without executing first
- Manual recipe construction

---

#### `list_recipes`
List all available recipes

**Parameters:**
- `limit` (optional): Max results (default: 50)

**Returns:** List of recipes with:
- ID, name, description
- Command count
- Usage statistics (times used, last used)
- Creation date

**Example:**
```
Show me all available recipes
List my automation recipes
```

---

#### `get_recipe`
Get detailed recipe information

**Parameters:**
- `recipe_id` (required): Recipe ID

**Returns:**
- Full recipe details
- Complete command sequence
- Prerequisites and success criteria
- Usage statistics

**Example:**
```
Show me details of recipe 3
What's in the wifi_diagnostics recipe?
```

---

#### `update_recipe`
Update an existing recipe in-place (preserves ID and usage stats)

**Parameters:**
- `recipe_id` (required): Recipe ID to update
- `name` (optional): New recipe name
- `description` (optional): New description
- `commands` (optional): New command sequence (replaces all commands)
- `prerequisites` (optional): New prerequisites
- `success_criteria` (optional): New success criteria

**Returns:**
- Updated recipe details
- Confirmation message

**Important:** 
- Only updates fields you specify - others remain unchanged
- Preserves: recipe ID, created_at, times_used, last_used_at
- This modifies the recipe in-place (old version not saved)
- To keep both versions, use `create_recipe_from_commands` instead

**Examples:**
```
Update recipe 4 to change the description
Fix the commands in recipe 3
Rename recipe 5 to 'postgres_diagnostics_v2'
```

---

#### `delete_recipe`
Delete a recipe permanently with confirmation (hard delete)

**Parameters:**
- `recipe_id` (required): Recipe ID to delete
- `confirm` (optional): Confirmation flag (default: false)

**Returns:**
- First call (confirm=false): Shows recipe details and asks for confirmation
- Second call (confirm=true): Deletes recipe and confirms

**Two-Step Process:**
1. Call without confirm → See what will be deleted
2. Call with confirm=true → Actually delete

**Important:** 
- This is a PERMANENT hard delete (not recoverable)
- Recipe is completely removed from database
- Two-step confirmation prevents accidents

**Examples:**
```
Delete recipe 3
Delete recipe 5 with confirmation
```

---

#### `execute_recipe`
Execute a saved recipe

**Parameters:**
- `recipe_id` (required): Recipe to execute
- `server_identifier` (optional): Server to run on (default: current)
- `start_conversation` (optional): Track in conversation (default: false)
- `conversation_goal` (optional): Goal if starting conversation

**Returns:** Execution results (commands run, status, output)

**Examples:**
```
Execute recipe 3
Run the wifi_diagnostics recipe on my server
Execute recipe 5 and track in a conversation
```

---

## Batch Script Management Features

### Key Features

**Automatic Deduplication:**
- Scripts are deduplicated via SHA256 content hash
- Same script content = same database entry
- Usage statistics tracked per unique script

**Usage Statistics:**
- `times_used`: How many times script has been executed
- `last_used_at`: Timestamp of most recent execution
- Helps identify popular/useful scripts

**Edit Mode:**
- Load existing script by ID in save_batch_script
- Modify and save (creates new version if content changed)
- Preserves script library organization

**Database Integration:**
- All scripts stored in `batch_scripts` table
- Execution history in `batch_executions` table
- Full command tracking in `commands` table

### Typical Workflow

1. **Create and execute:**
   ```
   Run docker diagnostics
   [Script executes, auto-saved to database]
   ```

2. **Browse library:**
   ```
   List my batch scripts
   [Shows all saved scripts with stats]
   ```

3. **Reuse script:**
   ```
   Execute script 5
   [Loads from database, runs, increments usage counter]
   ```

4. **Edit script:**
   ```
   Load script 5 for editing
   [Modifies content in UI]
   Save updated script
   [New version saved if content changed]
   ```

5. **Clean up:**
   ```
   Delete old script 3
   [Two-step confirmation, permanent delete]
   ```

---

## Usage Patterns

### Typical Workflow Examples

#### System Diagnostics
```
1. Connect to server
2. Execute batch diagnostic script
3. Review results
4. Take action based on findings
```

#### Software Installation
```
1. Start conversation: "Install nginx"
2. Check if already installed
3. Install if needed
4. Configure
5. Verify working
6. End conversation: success
7. Create recipe from conversation
```

#### Multi-Server Task
```
1. List all servers
2. Select first server
3. Execute commands
4. Select next server
5. Repeat commands
```

#### File Deployment
```
1. Upload directory with project files
2. Extract/configure on server
3. Test functionality
4. Download logs/results
```

---

## Output Filtering Rules

### What Gets Filtered (Claude's View)

| Command Pattern | Full Output | Claude Gets | Method |
|----------------|-------------|-------------|---------|
| `apt/yum install` | 500+ lines | Result summary | 3 lines |
| `pip install` | 200+ lines | Result summary | 3 lines |
| `ls -la` large dir | 150+ files | Stats + samples | 30 lines |
| `find /` | 1000+ results | Summary + samples | 50 lines |
| `cat` large file | 1000+ lines | Head + tail | 50 lines |
| `grep` many matches | 500+ lines | Pattern summary | 20 lines |

### What's Never Filtered

- **Any error** → Full error context always sent
- **Short output** → <50 lines sent complete
- **Explicit full request** → get_command_output available
- **Batch output_mode=full** → Complete output returned

---

## Database Tables

### Schema Overview

```sql
-- Server fingerprints (hardware/OS identity)
machines (id, machine_id, hostname, first_seen, last_seen)

-- Command history
commands (id, machine_id, conversation_id, command_text, result_output, 
          has_errors, error_context, backup_file_path, status, timestamp)

-- Grouped command sequences
conversations (id, machine_id, goal_summary, status, created_at, 
               completed_at, user_notes)

-- Reusable automation
recipes (id, name, description, prerequisites, success_criteria,
         created_from_conversation, times_used, last_used)

-- Recipe command sequences
recipe_commands (id, recipe_id, sequence_num, command_text)

-- Batch script library
batch_scripts (id, name, description, script_content, content_hash,
               created_by, created_at, times_used, last_used_at)

-- Batch execution tracking
batch_executions (id, machine_id, script_name, status, created_by,
                  started_at, completed_at, duration_seconds)
```

---

## Configuration Options

### config.yaml Key Settings

```yaml
connection:
  keepalive_interval: 30
  connection_timeout: 10

command_execution:
  default_timeout: 10        # Default command timeout
  max_timeout: 3600         # Maximum allowed

claude:
  auto_send_errors: true
  thresholds:
    install: 100            # Filter threshold for installs
    file_listing: 50        # Filter threshold for ls/find
    generic: 50            # Default threshold
  truncation:
    head_lines: 30         # Lines to keep at start
    tail_lines: 20         # Lines to keep at end

server:
  host: localhost
  port: 8080
  auto_open_browser: true  # Auto-open web terminal
```

---

**Version:** 3.1  
**Last Updated:** December 16, 2024
