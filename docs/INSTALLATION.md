# Remote Terminal - Installation Guide

Complete step-by-step installation instructions for the Remote Terminal MCP server.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation Steps](#installation-steps)
3. [Configuration](#configuration)
4. [Claude Desktop Setup](#claude-desktop-setup)
5. [Verification](#verification)
6. [Standalone Mode](#standalone-mode)
7. [Upgrading](#upgrading)
8. [Uninstallation](#uninstallation)

---

## System Requirements

### Local Machine (Windows)

- **OS:** Windows 10/11
- **Python:** 3.9 or higher
- **RAM:** 2GB minimum, 4GB recommended
- **Disk:** 500MB free space
- **Software:** 
  - Python (with pip)
  - Claude Desktop app
  - Modern web browser (Chrome, Firefox, Edge)

### Remote Server (Linux)

- **OS:** Any modern Linux distribution (Ubuntu, Debian, CentOS, RHEL, etc.)
- **SSH:** OpenSSH server running on port 22 (or custom port)
- **Access:** User account with SSH access (sudo recommended for full features)
- **Network:** Accessible from your local machine

---

## Installation Steps

### Step 1: Create Installation Directory

Choose a location for your Remote Terminal installation. This directory will contain:
- Python virtual environment
- Configuration files (config.yaml, hosts.yaml)
- Database (command history, recipes, scripts)

```powershell
# Recommended location
mkdir C:\RemoteTerminal
cd C:\RemoteTerminal
```

**Alternative locations work fine** - just use consistent paths in later steps.

### Step 2: Create Virtual Environment

```powershell
# Create isolated Python environment
python -m venv remote-terminal-env
```

**If you get an error:**
- Verify Python is installed: `python --version`
- Python 3.9+ required
- Add Python to PATH if needed

### Step 3: Activate Virtual Environment

```powershell
# Activate (PowerShell)
remote-terminal-env\Scripts\Activate
```

**If you get execution policy error:**
```powershell
# Run this once (as Administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then retry activation
remote-terminal-env\Scripts\Activate
```

You should see `(remote-terminal-env)` prefix in your prompt.

### Step 4: Install Package

With virtual environment activated:

```powershell
# Install from PyPI
pip install remote-terminal-mcp
```

**Expected output:**
- Multiple packages installing
- No errors
- "Successfully installed remote-terminal-mcp..." message

### Step 5: Verify Installation

```powershell
# Check installation
pip show remote-terminal-mcp

# Verify executables exist
where remote-terminal-mcp
where remote-terminal-standalone
```

Should show paths to the installed executables.

---

## Configuration

### Automatic First-Run Setup

**Remote Terminal uses automatic configuration setup:**

On first run, configuration files automatically copy from package templates to your working directory:
- `config.yaml` - Default settings (auto-created)
- `hosts.yaml` - Server template (auto-created)

**No manual file creation needed!**

### Step 1: Configure Claude Desktop (Required First)

Before running Remote Terminal, configure Claude Desktop to set the working directory.

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```powershell
# Open in Notepad
notepad %APPDATA%\Claude\claude_desktop_config.json
```

**Add this configuration:**

```json
{
  "mcpServers": {
    "remote-terminal": {
      "command": "C:\\RemoteTerminal\\remote-terminal-env\\Scripts\\remote-terminal-mcp.exe",
      "env": {
        "REMOTE_TERMINAL_ROOT": "C:\\RemoteTerminal"
      }
    }
  }
}
```

**Important Notes:**
- Replace `C:\RemoteTerminal` with your actual installation path from Step 1
- Use double backslashes (`\\`) in Windows paths
- The `REMOTE_TERMINAL_ROOT` tells Remote Terminal where to store config files
- JSON syntax must be valid (commas, quotes, brackets)

**If file already has other MCP servers:**

Add remote-terminal to the existing `mcpServers` section:

```json
{
  "mcpServers": {
    "some-other-server": {
      "command": "...",
      "args": ["..."]
    },
    "remote-terminal": {
      "command": "C:\\RemoteTerminal\\remote-terminal-env\\Scripts\\remote-terminal-mcp.exe",
      "env": {
        "REMOTE_TERMINAL_ROOT": "C:\\RemoteTerminal"
      }
    }
  }
}
```

### Step 2: Validate Configuration

Check JSON syntax:

```powershell
# This will show errors if JSON is malformed
Get-Content $env:APPDATA\Claude\claude_desktop_config.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Expected output:** No errors, shows parsed JSON

**If errors:**
- Check for missing commas
- Verify quote marks
- Ensure brackets/braces match
- Use JSON validator online if needed

### Step 3: Restart Claude Desktop

1. **Completely exit Claude Desktop:**
   - Right-click Claude icon in system tray
   - Click "Exit" or "Quit"
   - Or use Task Manager to end the process

2. **Start Claude Desktop again**

3. **Configuration files auto-create:**
   - On first connection, Remote Terminal creates:
     - `C:\RemoteTerminal\config.yaml`
     - `C:\RemoteTerminal\hosts.yaml`

### Step 4: Configure Your Servers

After first run, edit `C:\RemoteTerminal\hosts.yaml`:

```yaml
# Remote Terminal Hosts Configuration
# Version: 1.1.3 - Auto-config with user data preservation

servers:
  # Example server 1
  - name: production-server
    host: 192.168.1.100
    port: 22
    user: admin
    password: your_password_here
    description: Main production server
    tags: production, critical
  
  # Example server 2  
  - name: dev-server
    host: 192.168.1.101
    port: 22
    user: developer
    password: dev_password
    description: Development environment
    tags: development, testing
  
  # Example server 3 (custom SSH port)
  - name: backup-server
    host: backup.example.com
    port: 2222
    user: backup
    password: backup_pass
    description: Backup server on custom port
    tags: backup
# Optional: Set default server for auto-connect
# Use list_servers to see which server is marked as [DEFAULT]
default_server: production-server
```

**Field Descriptions:**

- `name`: Friendly identifier (required, unique)
- `host`: IP address or hostname (required)
- `port`: SSH port (default: 22)
- `user`: SSH username (required)
- `password`: SSH password (required)
- `description`: Human-readable description (optional)
- `tags`: Comma-separated tags for organization (optional)

**default_server:** Specify which server to auto-select on startup (optional)

**Tags Usage:**
- Organize servers by environment (production, staging, dev)
- Group by function (database, web, backup)
- Select by tag: "Connect to production server"

### Step 5: Configure Settings (Optional)

Edit `C:\RemoteTerminal\config.yaml` for advanced customization:

```yaml
# Connection settings (apply to all servers)
connection:
  keepalive_interval: 30
  reconnect_attempts: 3
  connection_timeout: 10

# Command execution
command_execution:
  default_timeout: 10      # Default command timeout (seconds)
  max_timeout: 3600       # Maximum allowed (1 hour)
  prompt_grace_period: 0.3
  check_interval: 0.5
  max_command_history: 50
  cleanup_interval: 300
  warn_on_long_timeout: 60

# Claude integration
claude:
  auto_send_errors: true
  thresholds:
    install: 100           # Filter install commands >100 lines
    file_listing: 50       # Filter ls/find >50 lines
    generic: 50           # Default threshold
  truncation:
    head_lines: 30        # Keep first 30 lines when truncating
    tail_lines: 20        # Keep last 20 lines

# Web terminal server
server:
  host: localhost
  port: 8080
  auto_open_browser: true

# Standalone mode (separate ports to run alongside MCP)
standalone:
  terminal_port: 8082
  control_port: 8081

# Database
database:
  path: data/remote_terminal.db
  backup:
    enabled: true
    interval_days: 7
  maintenance:
    vacuum_on_startup: true
    optimize_interval_days: 30

# Logging
logging:
  level: INFO
  file: logs/remote_terminal.log
  max_size_mb: 10
  backup_count: 5
```

**Most users can leave config.yaml as default.**

---

## Configuration Files Location

Understanding where your configuration files are stored:

### User Configuration Directory

**Location:** Set by `REMOTE_TERMINAL_ROOT` environment variable in Claude Desktop config

**Files stored here:**
- `config.yaml` - Global settings
- `hosts.yaml` - Server configurations
- `data/remote_terminal.db` - Command history database

**Example:** If `REMOTE_TERMINAL_ROOT` is `C:\RemoteTerminal`:
```
C:\RemoteTerminal\
├── config.yaml
├── hosts.yaml
└── data\
    └── remote_terminal.db
```

### Package Template Files

**Location:** Inside the installed package (site-packages)

**Files:**
- `config/config.yaml` - Default template
- `config/hosts.yaml.example` - Server template

**These are read-only templates** used to create your user configuration files on first run.

### User Data Preservation

**Important:** Your configuration files in `REMOTE_TERMINAL_ROOT` are preserved when upgrading:

```powershell
# Upgrade package - your config files stay safe
pip install --upgrade remote-terminal-mcp
```

Your `config.yaml`, `hosts.yaml`, and database remain untouched.

---

## Claude Desktop Setup

Already completed in Configuration Step 1, but here's a summary:

### Configuration File Location

```
%APPDATA%\Claude\claude_desktop_config.json
```

Full path:
```
C:\Users\YOUR_USERNAME\AppData\Roaming\Claude\claude_desktop_config.json
```

### Required Configuration

```json
{
  "mcpServers": {
    "remote-terminal": {
      "command": "C:\\RemoteTerminal\\remote-terminal-env\\Scripts\\remote-terminal-mcp.exe",
      "env": {
        "REMOTE_TERMINAL_ROOT": "C:\\RemoteTerminal"
      }
    }
  }
}
```

### Key Points

- `command`: Path to the installed executable
- `REMOTE_TERMINAL_ROOT`: Where to store configuration files
- Double backslashes in Windows paths
- Must restart Claude Desktop after changes

---

## Verification

### Step 1: Check MCP Connection

Open Claude and ask:

```
Claude, can you see the remote-terminal MCP server?
```

**Expected response:**
Claude confirms it can see the remote-terminal server.

### Step 2: Verify Configuration Files

Check that files were auto-created:

```powershell
# Should exist after first Claude connection
dir C:\RemoteTerminal\config.yaml
dir C:\RemoteTerminal\hosts.yaml
```

### Step 3: Test Server Listing

In Claude:

```
List all configured servers
```

**Expected:** Claude shows all servers from your `hosts.yaml`

### Step 4: Test Command Execution

```
Execute the command 'whoami' on my server
```

**What should happen:**
1. Browser opens automatically to `http://localhost:8080`
2. Web terminal appears
3. Command executes: `$ whoami`
4. Output shown: your username
5. Claude responds with result

### Step 5: Test File Operations

```
List files in my home directory
```

**Expected:** Claude shows file listing

### Step 6: Test Batch Execution

```
Run a simple system diagnostic
```

**Expected:** 
- Multiple commands execute in sequence
- Progress shown in web terminal
- Claude summarizes results

---

## Standalone Mode

Remote Terminal includes a standalone web interface (without Claude integration).

### Starting Standalone Mode

```powershell
cd C:\RemoteTerminal

# Activate environment
remote-terminal-env\Scripts\activate

# Run standalone server
remote-terminal-standalone
```

### Using Standalone Mode

1. Browser opens automatically
2. Control Panel: `http://localhost:8081`
3. Web Terminal: `http://localhost:8082`
4. Test MCP tools directly
5. Execute commands manually

**Use cases:**
- Testing without Claude
- Development/debugging
- Direct server management
- Demonstrating capabilities

### Stopping Standalone Mode

Press `Ctrl+C` in the PowerShell window.

---

## Upgrading

### Upgrade Package

```powershell
cd C:\RemoteTerminal

# Activate environment
remote-terminal-env\Scripts\activate

# Upgrade to latest version
pip install --upgrade remote-terminal-mcp
```

**Your data is safe:**
- Configuration files preserved (`config.yaml`, `hosts.yaml`)
- Database preserved (`data/remote_terminal.db`)
- All user data in `REMOTE_TERMINAL_ROOT` remains intact

### After Upgrade

1. Check release notes for breaking changes
2. Review new config.yaml options (compare with template)
3. Restart Claude Desktop
4. Test basic functionality

---

## Uninstallation

### Step 1: Remove from Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

Remove the `remote-terminal` section from `mcpServers`.

Restart Claude Desktop.

### Step 2: Deactivate Virtual Environment

```powershell
# In project directory
deactivate
```

### Step 3: Delete Installation Directory

```powershell
# Delete entire installation directory
Remove-Item -Recurse -Force C:\RemoteTerminal
```

**Note:** This removes:
- Virtual environment
- Configuration files
- Database (all command history)
- All user data

```

---

## Post-Installation

### Recommended Next Steps

1. **Read the Quick Start Guide** - Learn basic usage
2. **Review USER_GUIDE.md** - Explore all features
3. **Test batch execution** - Try running diagnostics
4. **Create a recipe** - Save your first automation
5. **Set up conversations** - Practice command tracking

### Optional Enhancements

1. **Multiple Servers** - Add all your servers to hosts.yaml
2. **Custom Recipes** - Build your automation library
3. **Database Backups** - Set up regular backups of remote_terminal.db
4. **Explore Standalone Mode** - Familiarize yourself with the web interface

### Getting Help

- Check **TROUBLESHOOTING.md** for common issues
- Review example recipes in `recipes/` folder (if available)
- Check Claude Desktop logs: Help → Show Logs
- Verify configuration file syntax

---

## Troubleshooting

### Configuration Files Not Created

**Problem:** `config.yaml` or `hosts.yaml` don't exist after first run

**Solutions:**
1. Verify `REMOTE_TERMINAL_ROOT` is set correctly in Claude Desktop config
2. Check the directory exists: `C:\RemoteTerminal`
3. Check Claude Desktop logs for errors
4. Try restarting Claude Desktop
5. Check file permissions on the directory

### Connection Issues

**Problem:** Cannot connect to server

**Solutions:**
- Verify SSH credentials in `hosts.yaml`
- Test manual SSH: `ssh user@host`
- Check firewall allows port 22
- Verify server is reachable: `ping 192.168.1.100`
- Check SSH port: `Test-NetConnection -ComputerName 192.168.1.100 -Port 22`

### Web Terminal Not Opening

**Problem:** Browser doesn't open automatically

**Solutions:**
- Manually open: `http://localhost:8080`
- Check if port 8080 is in use: `netstat -ano | findstr :8080`
- Verify `auto_open_browser: true` in `config.yaml`

### Claude Not Responding

**Problem:** Claude doesn't execute commands

**Solutions:**
- Check Claude Desktop logs (Help → Show Logs)
- Verify MCP server appears in Claude settings
- Restart Claude Desktop completely (required to use Task Manager to kill the process)
- Check remote-terminal-mcp.exe runs: `remote-terminal-mcp.exe --help`

### Path Issues

**Problem:** Paths with spaces or special characters

**Solutions:**
- Use paths without spaces: `C:\RemoteTerminal` instead of `C:\Remote Terminal`
- If spaces required, use quotes in JSON config
- Verify double backslashes in all Windows paths

---

**Version:** 1.1.3 (Auto-config, user data preservation)  
**Last Updated:** December 20, 2024
