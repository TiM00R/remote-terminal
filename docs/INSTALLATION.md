# Remote Terminal - Installation Guide

Complete step-by-step installation instructions for the Remote Terminal MCP server.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation Steps](#installation-steps)
3. [Configuration](#configuration)
4. [Claude Desktop Setup](#claude-desktop-setup)
5. [Verification](#verification)
6. [Security Setup (SSH Keys)](#security-setup-ssh-keys)
7. [Standalone Mode](#standalone-mode)
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

### Step 1: Download Project

Download or clone the Remote Terminal project to your Windows machine.

**Recommended location:**
```
D:\Projects\remote_terminal
```

**Alternative locations work fine - just adjust paths in later steps.**

### Step 2: Create Virtual Environment

Open PowerShell and navigate to the project:

```powershell
cd D:\Projects\remote_terminal

# Create virtual environment
python -m venv .venv
```

**If you get an error:**
- Verify Python is installed: `python --version`
- Python 3.9+ required
- Add Python to PATH if needed

### Step 3: Activate Virtual Environment

```powershell
# Activate (PowerShell)
.\.venv\Scripts\Activate.ps1
```

**If you get execution policy error:**
```powershell
# Run this once (as Administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then retry activation
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` prefix in your prompt.

### Step 4: Install Dependencies

With virtual environment activated:

```powershell
# Install base dependencies
pip install -r requirements.txt

# Install MCP support
pip install mcp
```

**Expected output:**
- Multiple packages installing
- No errors
- "Successfully installed..." messages

### Step 5: Verify Installation

```powershell
# Check Python environment
python --version

# Verify key imports work
python -c "import paramiko; import fastapi; import mcp; print('All imports OK')"
```

Should print: `All imports OK`

---

## Configuration

### Step 1: Configure Servers

Edit `hosts.yaml` in the project root:

```yaml
# Remote Terminal Hosts Configuration
# Version: 3.0 - Multi-server support with machine identity tracking

servers:
  # Example server 1
  - name: production-server
    host: 192.168.1.100
    port: 22
    user: admin
    password: your_password_here
    description: Main production server
    default: true
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
```

**Field Descriptions:**

- `name`: Friendly identifier (required, unique)
- `host`: IP address or hostname (required)
- `port`: SSH port (default: 22)
- `user`: SSH username (required)
- `password`: SSH password (required, see security section for SSH keys)
- `description`: Human-readable description (optional)
- `default`: Auto-select on startup (optional, only one server)
- `tags`: Comma-separated tags for organization (optional)

**Tags Usage:**
- Organize servers by environment (production, staging, dev)
- Group by function (database, web, backup)
- Select by tag: "Connect to production server"

### Step 2: Configure Settings (Optional)

Edit `config.yaml` for advanced customization:

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

### Step 3: Test SSH Connection

Before configuring Claude, verify SSH works:

```powershell
# With .venv activated
python -c "from src.hosts_manager import HostsManager; from src.ssh_manager import SSHManager; hm = HostsManager('hosts.yaml'); s = hm.get_default(); print(f'Testing connection to {s.name}...'); mgr = SSHManager(s.host, s.user, s.password, s.port); print('Connected!' if mgr.connect() else 'Failed to connect'); mgr.disconnect()"
```

**Expected output:**
```
Testing connection to production-server...
Connected!
```

**If connection fails:**
- Verify host is reachable: `ping 192.168.1.100`
- Check SSH credentials
- Verify SSH port: `Test-NetConnection -ComputerName 192.168.1.100 -Port 22`
- Check firewall settings

---

## Claude Desktop Setup

### Step 1: Locate Claude Config File

The Claude Desktop configuration file is located at:

```
%APPDATA%\Claude\claude_desktop_config.json
```

Full path:
```
C:\Users\YOUR_USERNAME\AppData\Roaming\Claude\claude_desktop_config.json
```

**To open in Notepad:**
```powershell
notepad %APPDATA%\Claude\claude_desktop_config.json
```

### Step 2: Add MCP Server Configuration

Add the remote-terminal server to the config file.

**If file is empty or has only `{}`:**

```json
{
  "mcpServers": {
    "remote-terminal": {
      "command": "D:\\Projects\\remote_terminal\\.venv\\Scripts\\python.exe",
      "args": [
        "D:\\Projects\\remote_terminal\\src\\mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "D:\\Projects\\remote_terminal\\src"
      }
    }
  }
}
```

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
      "command": "D:\\Projects\\remote_terminal\\.venv\\Scripts\\python.exe",
      "args": [
        "D:\\Projects\\remote_terminal\\src\\mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "D:\\Projects\\remote_terminal\\src"
      }
    }
  }
}
```

**Important Notes:**
- Use double backslashes (`\\`) in Windows paths
- Adjust paths if you installed to different location
- Verify your Python path: `.venv\Scripts\python.exe` should exist
- JSON syntax must be valid (commas, quotes, brackets)

### Step 3: Validate Configuration

Check JSON syntax:

```powershell
# This will show errors if JSON is malformed
Get-Content $env:APPDATA\Claude\claude_desktop_config.json | ConvertFrom-Json
```

**Expected output:** No errors, shows parsed JSON

**If errors:**
- Check for missing commas
- Verify quote marks
- Ensure brackets/braces match
- Use JSON validator online if needed

### Step 4: Restart Claude Desktop

1. **Completely exit Claude Desktop:**
   - Right-click Claude icon in system tray
   - Click "Exit" or "Quit"
   - Or use Task Manager to end the process

2. **Start Claude Desktop again**

3. **Verify MCP connection:**
   - Look for connection indicator in Claude interface
   - Should show connected MCP servers
   - "remote-terminal" should be listed

---

## Verification

### Step 1: Check MCP Connection

Open Claude and ask:

```
Claude, can you see the remote-terminal MCP server?
```

**Expected response:**
Claude confirms it can see the remote-terminal server.

### Step 2: Test Command Execution

```
Execute the command 'whoami' on my server
```

**What should happen:**
1. Browser opens automatically to `http://localhost:8080`
2. Web terminal appears
3. Command executes: `$ whoami`
4. Output shown: your username
5. Claude responds with result

### Step 3: Test Server Listing

```
List all configured servers
```

**Expected:** Claude shows all servers from your `hosts.yaml`

### Step 4: Test File Operations

```
List files in my home directory
```

**Expected:** Claude shows file listing with sizes

### Step 5: Test Batch Execution

```
Run a simple system diagnostic
```

**Expected:** 
- Multiple commands execute in sequence
- Progress shown in web terminal
- Claude summarizes results

---

## Security Setup (SSH Keys)

For production use, SSH keys are more secure than passwords.

### Step 1: Generate SSH Key Pair (Windows)

```powershell
# Generate key (if you don't have one)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Default location: C:\Users\YOUR_USERNAME\.ssh\id_ed25519
```

Press Enter to accept defaults.

### Step 2: Copy Public Key to Server

```powershell
# Get your public key
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub

# Copy the output
```

On your Linux server:

```bash
# Create .ssh directory if needed
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Add your public key
echo "your_public_key_here" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### Step 3: Test SSH Key Authentication

```powershell
# Test connection (should not ask for password)
ssh user@your-server
```

### Step 4: Update hosts.yaml for SSH Keys

```yaml
servers:
  - name: production-server
    host: 192.168.1.100
    port: 22
    user: admin
    # Remove or comment out password
    # password: old_password
    
    # Add key path instead
    key_file: C:\Users\YOUR_USERNAME\.ssh\id_ed25519
    description: Production server (SSH key auth)
    tags: production
```

**Note:** Current version primarily uses password authentication. SSH key support may require code modifications. For now, keys work with manual SSH but not yet fully integrated with the MCP tools.

---

## Standalone Mode

Remote Terminal also includes a standalone web interface (without Claude integration).

### Starting Standalone Mode

```powershell
cd D:\Projects\remote_terminal

# Run the standalone server
.\start_standalone.ps1
```

### Using Standalone Mode

1. Browser opens to `http://localhost:8080`
2. See MCP Control Panel interface
3. Test MCP tools directly
4. View tool schemas
5. Execute commands manually

**Use cases:**
- Testing without Claude
- Development/debugging
- Direct server management
- Demonstrating capabilities

### Stopping Standalone Mode

Press `Ctrl+C` in the PowerShell window.

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

### Step 3: Delete Project Files

```powershell
# Delete entire project directory
Remove-Item -Recurse -Force D:\Projects\remote_terminal
```

**Note:** This removes all data including command history database.

### Step 4: Clean Up Batch Logs (Optional)

```powershell
# Remove batch execution logs
Remove-Item -Recurse -Force C:\Users\YOUR_USERNAME\mcp_batch_logs
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

1. **SSH Key Authentication** - More secure than passwords
2. **Multiple Servers** - Add all your servers to hosts.yaml
3. **Custom Recipes** - Build your automation library
4. **Database Backups** - Set up regular backups of remote_terminal.db

### Getting Help

- Check **TROUBLESHOOTING.md** for common issues
- Review example recipes in `recipes/` folder
- Examine batch script patterns
- Check Claude Desktop logs: Help → Show Logs

---

**Version:** 3.0 (SQLite-based, multi-server support)  
**Last Updated:** December 2024
