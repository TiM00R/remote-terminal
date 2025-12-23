# Remote Terminal - Quick Start Guide

Get Claude controlling your remote Linux server in 5 minutes!

## What Is This?

Remote Terminal lets Claude (the AI) execute commands on your remote Linux servers through a chat interface. You can ask Claude to check server status, install packages, troubleshoot problems, or run diagnostics - and Claude does the work for you.

**Key Features:**
- Claude executes commands on your behalf
- Watch full output in your browser in real-time
- Claude gets smart filtered summaries (saves 95% tokens)
- Track command history and conversation context
- Execute multi-command batch scripts
- Transfer files between local and remote

## Prerequisites

- Windows PC (local machine)
- Remote Linux server with SSH access
- Claude Desktop app installed
- Python 3.9+ installed

## 5-Minute Setup

### Step 1: Create Installation Directory

```powershell
# Choose a location (example: C:\RemoteTerminal)
mkdir C:\RemoteTerminal
cd C:\RemoteTerminal
```

### Step 2: Install Package

```powershell
# Create virtual environment
python -m venv remote-terminal-env

# Activate it
remote-terminal-env\Scripts\activate

# Install package
pip install remote-terminal-mcp
```

### Step 3: Configure Claude Desktop

1. Find your Claude config file:
   - Location: `%APPDATA%\Claude\claude_desktop_config.json`
   - Full path: `C:\Users\YOUR_USERNAME\AppData\Roaming\Claude\claude_desktop_config.json`

2. Open in Notepad:
   ```powershell
   notepad %APPDATA%\Claude\claude_desktop_config.json
   ```

3. Add this configuration:

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

**Important:** Replace `C:\RemoteTerminal` with your actual installation path from Step 1.

4. Save and close the file

### Step 4: Restart Claude Desktop

1. Completely exit Claude Desktop (right-click system tray → Exit)
2. Restart Claude Desktop (use Task Manager to kill the process)
3. Look for MCP connection indicator (small icon showing connected servers)

### Step 5: First Run - Auto Setup

On first use, configuration files will automatically copy to `C:\RemoteTerminal`:
- `config.yaml` - Default settings (auto-created)
- `hosts.yaml` - Server list (auto-created from template)

### Step 6: Configure Your Server

Edit `C:\RemoteTerminal\hosts.yaml`:

```yaml
servers:
  - name: my-server
    host: 192.168.1.100
    user: your_username
    password: your_password
    port: 22
    description: My Linux server
    tags: production
# Optional: Set default server for auto-connect
default_server: my-server
```

**Security Note:** For production use, consider SSH keys instead of passwords.

### Step 7: Restart Claude Again

Restart Claude Desktop to load your server configuration.

### Step 8: Test It!

Open Claude and try:

```
Claude, list my configured servers
```

Claude should show your server from `hosts.yaml`.

Then try:

```
Execute the command 'whoami' on my server
```

**What happens:**
1. Browser automatically opens to `http://localhost:8080`
2. Web terminal shows the command executing
3. You see output: your username
4. Claude responds with the result

## What You Just Enabled

You can now ask Claude things like:

**System Info:**
```
What's the disk space on my server?
Show me CPU and memory usage
What Linux version is running?
```

**Troubleshooting:**
```
Check if nginx is running
Show me the last 50 lines of the system log
Find all Python processes
```

**Software Management:**
```
Install htop
Check if docker is installed
Update all packages
```

**File Operations:**
```
List files in /var/log modified today
Show me the nginx config file
Find all .log files larger than 100MB
```

**Diagnostics:**
```
Run complete network diagnostics
Check all running services
Analyze disk usage by directory
```

## Understanding the Output

When Claude executes commands, you get TWO views:

### 1. Web Terminal (Your View)
- Opens automatically in browser at `http://localhost:8080`
- Shows FULL command output in real-time
- No filtering - you see everything
- Stays open for entire session

### 2. Claude's View (Smart Filtered)
- Claude receives optimized summaries
- Saves ~95% tokens on verbose commands
- Errors always sent in full (Claude needs context)
- Short output (<50 lines) sent complete

**Example:**

When Claude runs `sudo apt install nginx`:
- **You see:** All 500+ lines of installation output streaming
- **Claude gets:** "nginx installed successfully in 45s"

This means:
- You maintain full visibility and control
- Claude works efficiently without token waste
- Best of both worlds!

## Configuration Files Location

Your configuration files are stored in `C:\RemoteTerminal` (or wherever you set `REMOTE_TERMINAL_ROOT`):

- `config.yaml` - Global settings (timeouts, filtering, ports)
- `hosts.yaml` - Your server configurations
- `data/remote_terminal.db` - Command history database

**Important:** These files are preserved when you upgrade the package via `pip install --upgrade remote-terminal-mcp`.

## Next Steps

Now that you're running, explore the other guides:

- **INSTALLATION.md** - Detailed installation instructions
- **USER_GUIDE.md** - Complete feature walkthrough
- **TROUBLESHOOTING.md** - Common problems and solutions
- **FEATURE_REFERENCE.md** - All MCP tools reference

## Quick Reference

### Useful Commands to Try

**System Health Check:**
```
Claude, run a complete system health check on my server
```

**Find Large Files:**
```
Find files larger than 1GB in the home directory
```

**Service Management:**
```
Restart the nginx service and verify it's running
```

**Log Analysis:**
```
Show me any errors in the last hour of system logs
```

## Optional: Standalone Mode

You can also run Remote Terminal's web interface directly (without Claude):

```powershell
cd C:\RemoteTerminal
remote-terminal-env\Scripts\activate
remote-terminal-standalone
```

Access at:
- Control Panel: http://localhost:8081
- Terminal: http://localhost:8082

## Need Help?

**Connection Issues?**
- Verify SSH credentials in `hosts.yaml`
- Test manual SSH connection: `ssh user@host`
- Check firewall allows port 22

**Web Terminal Not Opening?**
- Manually open: `http://localhost:8080`
- Check if port 8080 is in use

**Claude Not Responding?**
- Check Claude Desktop logs (Help → Show Logs)
- Verify MCP server appears in Claude settings
- Restart Claude Desktop completely

**Config Files Not Created?**
- Check `REMOTE_TERMINAL_ROOT` is set correctly in Claude Desktop config
- Verify the directory exists: `C:\RemoteTerminal`
- Check Claude Desktop logs for errors

---

**You're all set!** Start asking Claude to help with your Linux server management.

**Version:** 1.1.3 (Auto-config, user data preservation)  
**Last Updated:** December 20, 2024
