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

### Step 1: Download and Extract

1. Extract the `remote_terminal` folder to: `D:\Projects\remote_terminal`
2. Or choose your own location (adjust paths below accordingly)

### Step 2: Configure Your Server

Edit `D:\Projects\remote_terminal\hosts.yaml`:

```yaml
servers:
  - name: my-server
    host: 192.168.1.100
    user: your_username
    password: your_password
    port: 22
    description: My Linux server
    default: true
    tags: production
```

**Security Note:** For production use, consider SSH keys instead of passwords.

### Step 3: Install Dependencies

Open PowerShell and run:

```powershell
cd D:\Projects\remote_terminal

# Create virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install MCP support
pip install mcp
```

### Step 4: Test Connection

```powershell
# Still in PowerShell with .venv activated
python -c "from src.hosts_manager import HostsManager; from src.config import Config; from src.ssh_manager import SSHManager; hm = HostsManager('hosts.yaml'); s = hm.get_default(); mgr = SSHManager(s.host, s.user, s.password); print('Connected!' if mgr.connect() else 'Failed')"
```

You should see: `Connected!`

### Step 5: Configure Claude Desktop

1. Find your Claude config file:
   - Location: `%APPDATA%\Claude\claude_desktop_config.json`
   - Full path: `C:\Users\YOUR_USERNAME\AppData\Roaming\Claude\claude_desktop_config.json`

2. Open in Notepad:
   ```powershell
   notepad %APPDATA%\Claude\claude_desktop_config.json
   ```

3. Add this configuration (adjust paths if you installed elsewhere):

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

4. Save and close the file

### Step 6: Restart Claude Desktop

1. Completely exit Claude Desktop (right-click system tray → Exit)
2. Restart Claude Desktop
3. Look for MCP connection indicator (small icon showing connected servers)

### Step 7: Test It!

Open Claude and try:

```
Claude, can you check if you're connected to my remote terminal?
```

Claude should confirm it can see the `remote-terminal` MCP server.

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

## Next Steps

Now that you're running, explore the other guides:

- **USER_GUIDE.md** - Complete feature walkthrough
- **TROUBLESHOOTING.md** - Common problems and solutions
- **ADVANCED_FEATURES.md** - Conversations, recipes, batch execution

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

## Need Help?

**Connection Issues?**
- Verify SSH credentials in `hosts.yaml`
- Test manual SSH connection: `ssh user@host`
- Check firewall allows port 22

**Web Terminal Not Opening?**
- Manually open: `http://localhost:8080`
- Check if port 8080 is in use: `netstat -ano | findstr :8080`

**Claude Not Responding?**
- Check Claude Desktop logs (Help → Show Logs)
- Verify MCP server appears in Claude settings
- Restart Claude Desktop completely

---

**You're all set!** Start asking Claude to help with your Linux server management.

**Version:** 3.0 (SQLite-based, multi-server support)  
**Last Updated:** December 2024
