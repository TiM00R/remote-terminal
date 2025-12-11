# Remote Terminal - Complete User Guide

Comprehensive guide to all features of the Remote Terminal MCP integration with Claude.

## Table of Contents

1. [Overview](#overview)
2. [Basic Usage](#basic-usage)
3. [Multi-Server Management](#multi-server-management)
4. [Command Execution](#command-execution)
5. [File Transfer (SFTP)](#file-transfer-sftp)
6. [Batch Script Execution](#batch-script-execution)
7. [Conversations & Tracking](#conversations--tracking)
8. [Recipes & Automation](#recipes--automation)
9. [Web Terminal Interface](#web-terminal-interface)
10. [Advanced Features](#advanced-features)

---

## Overview

Remote Terminal is an MCP (Model Context Protocol) server that lets Claude execute commands on your remote Linux servers. It provides a dual-stream architecture where you see full output in a web terminal while Claude receives smart-filtered summaries optimized for token efficiency.

### Key Capabilities

- **Command Execution:** Run any bash command remotely
- **Multi-Server Support:** Manage multiple servers with easy switching
- **File Transfer:** Upload/download files and directories via SFTP
- **Batch Execution:** Run multi-command scripts as atomic operations
- **Conversation Tracking:** Group related commands by goal with rollback support
- **Recipe System:** Save successful command sequences for reuse
- **Smart Filtering:** 95% token reduction on verbose output
- **Database Integration:** Full command history and audit trail (SQLite)

---

## Basic Usage

### Your First Commands

Once configured, simply ask Claude natural language questions:

```
Check the disk space on my server
```

Claude will:
1. Open web terminal in your browser (first time only)
2. Execute `df -h` command
3. Show you full output in web terminal
4. Summarize results in chat

### Simple Examples

**System Information:**
```
What's my username?
Show me the current date and time
What Linux version is running?
```

**Process Management:**
```
What processes are using the most CPU?
Show me all Python processes
Kill process 1234
```

**File System:**
```
List files in my home directory
Show hidden files in /etc
Find all .log files in /var/log
```

---

## Multi-Server Management

### Managing Multiple Servers

Remote Terminal supports managing multiple servers defined in `hosts.yaml`.

#### Viewing Servers

Ask Claude:
```
List all my configured servers
```

Claude will show you all servers from `hosts.yaml` with their connection status.

#### Switching Servers

```
Connect to my-production-server
```

or

```
Switch to the server tagged 'development'
```

Claude will:
- Disconnect from current server (if any)
- Connect to the specified server
- Fetch and store the machine identity (hardware/OS fingerprint)
- Update web terminal display

#### Server Selection Methods

You can select servers by:
- **Name:** `Connect to my-server`
- **Host/IP:** `Connect to 192.168.1.100`
- **Tag:** `Connect to the production server`

#### Machine Identity

Each server has a unique machine_id (hardware + OS fingerprint) stored in the database. This ensures:
- Commands are tracked per physical machine
- Conversations are machine-specific
- Recipes work on compatible systems
- Audit trail maintains integrity

**Force Identity Check:**

If you swap hardware at the same IP address:
```
Connect to my-server and verify its identity
```

Claude will re-read the machine_id from the actual server instead of using cache.

### Default Server

Set a default server in `hosts.yaml`:

```yaml
servers:
  - name: my-server
    host: 192.168.1.100
    default: true
```

Claude will NOT auto-connect to this server on startup, you must explicitly select it when needed.

---

## Command Execution

### Basic Command Execution

```
Run the command 'ls -la' on my server
```

### Command Options

#### Timeout Control

Default timeout is 10 seconds. For long-running commands:

```
Install nginx (this might take a while)
```

Claude will automatically use appropriate timeout (installation commands get longer timeouts).

Maximum timeout: 3600 seconds (1 hour)

#### Output Modes

**Auto Mode (default):**
- Smart decision based on output length
- <100 lines: full output
- ≥100 lines: preview only
- Installation commands: result summary

**Preview Mode:**
```
Show me first and last 10 lines of the syslog
```

**Full Mode:**
```
I need to see the complete nginx config file
```

Claude receives full unfiltered output (uses more tokens).

### Background Commands

Long-running commands can be monitored:

```
Start a system update in the background
```

Claude will:
1. Start the command
2. Return immediately with command ID
3. You can check status later

Check status:
```
What's the status of command abc123?
```

### Canceling Commands

To stop a running command:
```
Cancel the current command
```

or
```
Send Ctrl+C to stop it
```

---

## File Transfer (SFTP)

Remote Terminal includes powerful SFTP capabilities for transferring files and directories.

### Single File Upload

```
Upload C:\Users\WindowsUser\config.json to /home/linuxuser/config.json on the server
```

Options:
- Preserves timestamps by default
- Overwrites existing files by default
- Can set permissions (chmod)

### Single File Download

```
Download /var/log/syslog to C:\Logs\syslog
```

### Directory Upload

```
Upload D:\Projects\myapp to /home/linuxuser/myapp
```

**Smart Features:**
- Automatic compression for large transfers (>10MB)
- Progress tracking with ETA
- Automatic exclusion of .git, node_modules, __pycache__, etc.
- Background mode for large transfers

**Conflict Resolution:**
- `merge` (default): Keep newer files
- `overwrite`: Replace all
- `skip`: Don't replace existing
- `error`: Fail if exists

### Directory Download

```
Download /home/linuxuser/myapp to D:\Projects\myapp
```

Same smart features as upload.

### Directory Listing

```
List files in /var/log
Show hidden files in /etc
```

With details:
```
Get detailed info about /home/linuxuser/config.json
```

---

## Batch Script Execution

Execute multiple related commands as a single atomic operation.

### Why Batch Execution?

**Problem:** Running 10 diagnostic commands sequentially:
- 10 commands × 30 seconds each = 5 minutes total
- 10 round-trips with Claude thinking time
- Poor user experience

**Solution:** Batch execution:
- All 10 commands in one script = 30 seconds total
- 1 round-trip
- User sees live progress

**Speed improvement: 10-50x faster!**

### Basic Example

```
Run network diagnostics
```

Claude creates and executes:
```bash
#!/bin/bash
set -e
echo "=== [STEP 1/5] Check interfaces ==="
ip link show
echo "[STEP_1_COMPLETE]"

echo "=== [STEP 2/5] Check routing ==="
ip route show
echo "[STEP_2_COMPLETE]"

# ... more steps ...

echo "[ALL_DIAGNOSTICS_COMPLETE]"
```

### What You See

**Web Terminal:**
- All commands executing in sequence
- Real-time output streaming
- Step markers showing progress

**Claude's Response:**
```
Network diagnostics completed in 2.3 seconds

Steps completed: 5/5
Errors detected: No

Summary:
- 3 network interfaces found
- Default route via 192.168.1.1
- DNS: 8.8.8.8, 8.8.4.4
- All connectivity tests passed

Full log saved to: C:\Users\WindowsUser\mcp_batch_logs\batch_output_1732123456.log
```

### Output Modes

**Summary Mode (default):**
- Steps completed, errors, execution time
- Preview: first/last 10 lines
- Full log saved locally
- Token efficient

**Full Mode:**
- Complete output in response
- For diagnostic commands with expected concise output
- AI can analyze immediately
- Uses more tokens

Example:
```
Run complete network diagnostics and show me everything
```

### Batch Use Cases

**System Diagnostics:**
- Network troubleshooting
- Service status checks
- Resource monitoring
- Hardware detection

**Package Investigation:**
- Check installed packages
- Version comparisons
- Dependency analysis

**Log Collection:**
- Multiple log files
- System events
- Application logs
- Error searching

**Common Patterns:**

```
Check WiFi hardware and drivers
Investigate docker installation and status
Collect all nginx-related logs and configs
Run complete system health check
```

### Local Log Files

All batch executions are saved:
```
C:\Users\WindowsUser\mcp_batch_logs\
├── batch_output_1732123456.log
├── batch_output_1732123789.log
└── batch_output_1732124000.log
```

You can review these later or share them for troubleshooting.

---

## Conversations & Tracking

Group related commands by goal, track progress, and enable rollback.

### What Are Conversations?

A conversation groups commands that work toward a single goal:
- "Configure WiFi"
- "Install and configure Docker"
- "Debug nginx issues"

Benefits:
- Organized command history
- Rollback capability
- Recipe generation from successful patterns
- Better context for AI

### Starting a Conversation

```
Start a conversation to configure WiFi
```

Claude will:
1. Create conversation with goal "configure WiFi"
2. Check if there's already a conversation in progress
3. Return conversation_id
4. Track all subsequent commands automatically

### Conversation Workflow

**When you select a server:**

If open conversations exist, Claude will:
1. Stop and present the list
2. Ask you to choose:
   - Resume specific conversation: "resume conversation 5"
   - Start new: "start new conversation for [goal]"
   - No conversation: "run commands without conversation"

**Your choice persists** for all commands on that server until:
- You switch servers
- You explicitly change mode
- New Claude dialog starts

### Resuming Conversations

```
Resume conversation 5
```

or

```
Continue our WiFi configuration from yesterday
```

Claude will load the conversation context and continue tracking.

### Ending Conversations

```
End the conversation - it worked!
```

or

```
End the conversation - didn't solve the problem
```

Status options:
- `success`: Goal achieved
- `failed`: Didn't work
- `rolled_back`: Commands were undone

### Viewing Conversation History

```
Show me all my conversations
```

or

```
List successful conversations from last week
```

Claude will show:
- Conversation goals
- Status (in_progress, success, failed, rolled_back)
- Command count
- Date/time

### Reviewing Conversation Commands

```
Show me all commands from conversation 5
```

Claude displays:
- Sequence of commands executed
- Results of each
- Error detection flags
- Backup locations (if files were modified)

---

## Recipes & Automation

Save successful command sequences for reuse.

### What Are Recipes?

Recipes are reusable automation templates created from successful conversations:
- Network diagnostics
- Service installation procedures
- System health checks
- Configuration workflows

### Creating Recipes

After a successful conversation:

```
Create a recipe from conversation 5 named 'wifi_diagnostics'
```

Claude will:
1. Extract command sequence
2. Save as reusable recipe
3. Document prerequisites and success criteria

### Using Recipes

```
Execute the wifi_diagnostics recipe
```

or

```
Run network diagnostics recipe on this server
```

Claude will:
1. Load recipe
2. Execute commands in sequence
3. Track execution (optionally in new conversation)
4. Report results

### Listing Recipes

```
Show me all available recipes
```

Claude displays:
- Recipe names and descriptions
- Command counts
- Usage statistics (times used, last used)
- Prerequisites

### Recipe Details

```
Show me details of the wifi_diagnostics recipe
```

Claude shows:
- Complete command sequence
- Prerequisites (OS requirements, permissions)
- Success criteria (how to verify it worked)
- Creation date and source conversation

### Example Recipes

**Network Diagnostics:**
```
Commands:
1. ip link show
2. ip addr show
3. ip route show
4. cat /etc/resolv.conf
5. ping -c 3 8.8.8.8

Prerequisites: Linux with ip command
Success: All commands complete, connectivity verified
```

**Docker Installation Check:**
```
Commands:
1. docker --version
2. systemctl status docker
3. docker ps
4. docker images

Prerequisites: Docker should be installed
Success: Docker running, responsive
```

---

## Web Terminal Interface

The web terminal provides full visibility into command execution.

### Auto-Opening

On first command execution:
1. Browser automatically opens
2. URL: `http://localhost:8080`
3. Stays open for entire session
4. No need to reopen

### What You See

```
┌─────────────────────────────────────────────┐
│ Remote Terminal                             │
│                       Connected: obd@server │
├─────────────────────────────────────────────┤
│                                             │
│ $ whoami                                    │
│ obd                                         │
│                                             │
│ $ df -h                                     │
│ Filesystem      Size  Used Avail Use%       │
│ /dev/sda1        50G   20G   28G  42%       │
│                                             │
└─────────────────────────────────────────────┘
```

### Features

- **Real-time output:** See commands as they execute
- **Full visibility:** No filtering - complete output
- **Connection status:** Shows current server
- **Command history:** Scrollback through all commands
- **Color support:** Terminal colors preserved
- **Responsive:** Updates instantly

### Manual Access

If auto-open fails, manually open:
```
http://localhost:8080
```

### Shared Connection

Web terminal shares the same SSH connection as Claude:
- Commands from Claude appear in web terminal
- Same prompt detection
- Synchronized state
- Single SSH session

### Multi-Terminal Synchronization

Open the same terminal URL in multiple browser windows - they all stay perfectly synchronized via WebSocket broadcast.

**How it works:**
- All terminals connect via WebSocket to the same server
- SSH output broadcasts to ALL connected terminals simultaneously  
- Input from ANY terminal appears in ALL terminals instantly
- Clean disconnect when closing browser tabs

**Benefits:**
- **Multi-monitor support:** Watch same session on multiple screens
- **Collaboration:** Multiple people can view the same session (share your screen or send URL)
- **Backup terminal:** Keep an extra window open for safety
- **Real-time sync:** Type in window 1, see it immediately in windows 2, 3, 4...

**Example use cases:**
- Monitor terminal on second screen while working on first
- Share terminal view with colleague (they can watch, you control)
- Keep backup window open during critical operations
- Present live command execution to a team

**Testing multi-terminal:**
1. Open http://localhost:8080 in Browser Window 1
2. Open http://localhost:8080 in Browser Window 2 (new tab/window)
3. Type "ls" in Window 1 → appears in Window 2 instantly
4. Run command → output appears in BOTH terminals
5. Claude executes command → output in ALL terminals

⚠️ **Best Practice:** Close unused terminal tabs when done. While the system efficiently handles multiple connections (tested with 10+ terminals), keeping many old tabs open can:
- Consume unnecessary system resources (memory ~50KB per terminal)
- Potentially cause WebSocket connection issues
- Create confusion about which terminals are active

**Clean up regularly:** Before starting a new session, close all old terminal tabs. This ensures optimal performance and prevents connection buildup.

**Technical details:** See [WEBSOCKET_BROADCAST.md](WEBSOCKET_BROADCAST.md) for complete architecture and troubleshooting information.

---

## Advanced Features

### Smart Output Filtering

Claude receives optimized summaries to save tokens.

#### What Gets Filtered

| Command Type | You See | Claude Gets | Savings |
|--------------|---------|-------------|---------|
| `apt install` | 500+ lines | "Success in 45s" | 96% |
| `ls -la` | 150 files | Stats + 20 samples | 95% |
| `find /` | 1000+ results | Summary + samples | 97% |
| `cat bigfile` | 1000+ lines | Head + tail | 97% |

#### What's Never Filtered

- **Errors:** Claude always gets full error context
- **Short output:** <50 lines sent complete
- **Explicit requests:** Full mode available

#### Requesting Full Output

```
Show me the complete unfiltered output
```

Claude uses the `get_raw_output` tool to receive everything.

### Command Status Tracking

Every command gets:
- Unique command ID
- Execution status (running, completed, cancelled, timeout)
- Output buffer (filterable)
- Error detection flags
- Timestamps
- Exit code

Check status:
```
What's the status of my last command?
List all running commands
```

### Database Integration

All operations are tracked in SQLite database (`data/remote_terminal.db`):

**Tables:**
- `servers`: Server machine identities (hardware/OS fingerprints)
- `conversations`: Conversation tracking by goal
- `commands`: Complete command execution history
- `recipes`: Saved automation templates
- `batch_executions`: Batch script execution tracking
- `batch_scripts`: Reusable batch script library

**Benefits:**
- Complete audit trail
- Command history searchable and filterable
- Conversation context preserved
- Recipe library with usage statistics
- Machine-specific tracking (per physical hardware)
- Batch execution progress monitoring

### Error Detection

Automatic error detection looks for:
- ERROR, FATAL, CRITICAL keywords
- "command not found"
- "Permission denied"
- "No such file"
- Non-zero exit codes

When errors detected:
- Full error context sent to Claude (never filtered)
- Last 20 lines before error included
- Error summary provided

### Configuration Options

Edit `config.yaml` for advanced customization:

```yaml
command_execution:
  default_timeout: 10
  max_timeout: 3600
  prompt_grace_period: 0.3
  
claude:
  auto_send_errors: true
  thresholds:
    install: 100
    file_listing: 50
    generic: 50
  truncation:
    head_lines: 30
    tail_lines: 20

server:
  host: localhost
  port: 8080
  auto_open_browser: true
```

### Security Considerations

**Passwords in Configuration:**
- Currently stored in plain text in `hosts.yaml`
- For production: Use SSH keys instead
- Consider encrypted storage solutions

**Network Security:**
- Web terminal bound to localhost only
- Not exposed to network
- SSH connection uses standard security

**Audit Trail:**
- All commands logged in database
- Review history for security audit
- Track who did what and when

---

## Tips & Best Practices

### For Users

1. **Keep web terminal open** - Monitor what Claude is doing
2. **Use conversations for multi-step tasks** - Better tracking and rollback
3. **Create recipes from successful workflows** - Reuse automation
4. **Trust the filtering** - Claude gets what it needs
5. **Review batch logs** - Full details saved locally

### For Claude Integration

1. **Batch when possible** - 10-50x faster than sequential
2. **Use conversations for complex goals** - Better context
3. **Trust filtered output** - Contains essential info
4. **Request raw output when needed** - Full visibility available
5. **Create recipes from success** - Build automation library

### Common Workflows

**Initial System Check:**
```
1. Connect to server
2. Run system diagnostics
3. Review status
```

**Software Installation:**
```
1. Start conversation: "Install and configure nginx"
2. Check if installed
3. Install if needed
4. Configure
5. Verify working
6. End conversation: success
7. Create recipe from conversation
```

**Troubleshooting:**
```
1. Start conversation: "Debug nginx issues"
2. Run diagnostics batch
3. Check logs
4. Try fixes
5. Verify
6. End conversation: status
```

**File Management:**
```
1. Upload local project files
2. Extract/configure
3. Test
4. Download logs/results
```

---

## Next Steps

- Explore **TROUBLESHOOTING.md** for common issues
- Review recipe examples in `recipes/` folder
- Check batch script patterns for common tasks
- Experiment with conversation tracking
- See **DATABASE_SCHEMA.md** for complete database documentation

---

**Version:** 3.0 (SQLite-based, multi-server support)  
**Last Updated:** December 2024
