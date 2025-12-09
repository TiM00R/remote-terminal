# Remote Terminal - Troubleshooting Guide

Solutions to common problems and error scenarios.

## Table of Contents

1. [Connection Issues](#connection-issues)
2. [Claude Desktop Integration](#claude-desktop-integration)
3. [Web Terminal Problems](#web-terminal-problems)
4. [Command Execution Issues](#command-execution-issues)
5. [File Transfer Problems](#file-transfer-problems)
6. [Batch Execution Errors](#batch-execution-errors)
7. [Database Issues](#database-issues)
8. [Performance Problems](#performance-problems)
9. [Configuration Errors](#configuration-errors)
10. [Debugging Tips](#debugging-tips)

---

## Connection Issues

### SSH Connection Failed

**Symptom:** Cannot connect to remote server

**Possible Causes & Solutions:**

1. **Incorrect credentials**
   ```
   Check hosts.yaml:
   - Verify username
   - Verify password
   - Check port number
   ```

2. **Server not reachable**
   ```powershell
   # Test network connectivity
   ping 192.168.1.100
   
   # Test SSH port
   Test-NetConnection -ComputerName 192.168.1.100 -Port 22
   ```

3. **Firewall blocking**
   - Check Windows Firewall
   - Check server firewall (iptables, ufw)
   - Check router/network firewall

4. **SSH server not running**
   ```bash
   # On remote server
   sudo systemctl status sshd
   sudo systemctl start sshd
   ```

5. **Wrong SSH port**
   ```yaml
   # hosts.yaml - if using custom port
   port: 2222  # Instead of default 22
   ```

### Connection Timeout

**Symptom:** Connection attempts time out

**Solution:**
```yaml
# Increase timeout in config.yaml
connection:
  connection_timeout: 30  # Increase from default 10
```

**Network issues:**
```powershell
# Check route to server
tracert 192.168.1.100

# Check for packet loss
ping -t 192.168.1.100
```

### Connection Drops Randomly

**Symptom:** Connection disconnects during use

**Solutions:**

1. **Adjust keepalive settings**
   ```yaml
   # config.yaml
   connection:
     keepalive_interval: 15  # More frequent keepalive
   ```

2. **Network stability**
   - Check WiFi signal strength
   - Use wired connection if possible
   - Check for network congestion

3. **Server-side timeout**
   ```bash
   # On remote server, edit /etc/ssh/sshd_config
   ClientAliveInterval 30
   ClientAliveCountMax 3
   
   # Restart SSH
   sudo systemctl restart sshd
   ```

### Permission Denied (publickey)

**Symptom:** SSH key authentication fails

**Solution:**

1. **Verify key permissions** (Linux/WSL):
   ```bash
   chmod 700 ~/.ssh
   chmod 600 ~/.ssh/id_ed25519
   chmod 644 ~/.ssh/id_ed25519.pub
   ```

2. **Verify authorized_keys on server**:
   ```bash
   # On remote server
   chmod 700 ~/.ssh
   chmod 600 ~/.ssh/authorized_keys
   
   # Verify your key is present
   cat ~/.ssh/authorized_keys
   ```

3. **Test manually**:
   ```powershell
   ssh -i $env:USERPROFILE\.ssh\id_ed25519 user@host
   ```

---

## Claude Desktop Integration

### MCP Server Not Appearing

**Symptom:** Claude doesn't see remote-terminal server

**Solutions:**

1. **Verify config file location**
   ```powershell
   # Should exist
   Test-Path $env:APPDATA\Claude\claude_desktop_config.json
   ```

2. **Check JSON syntax**
   ```powershell
   # Should parse without errors
   Get-Content $env:APPDATA\Claude\claude_desktop_config.json | ConvertFrom-Json
   ```

3. **Verify paths in config**
   ```powershell
   # Python executable should exist
   Test-Path "D:\Projects\remote_terminal\.venv\Scripts\python.exe"
   
   # MCP server script should exist
   Test-Path "D:\Projects\remote_terminal\src\mcp_server.py"
   ```

4. **Restart Claude completely**
   - Exit via system tray icon
   - Check Task Manager - end any Claude processes
   - Start Claude Desktop again

5. **Check Claude logs**
   - In Claude Desktop: Help → Show Logs
   - Look for MCP connection errors
   - Look for Python errors

### MCP Server Crashes on Start

**Symptom:** Server appears briefly then disappears

**Solutions:**

1. **Test Python environment**
   ```powershell
   cd D:\Projects\remote_terminal
   .\.venv\Scripts\Activate.ps1
   python src\mcp_server.py
   ```
   
   Look for error messages.

2. **Check dependencies**
   ```powershell
   pip list | findstr mcp
   pip list | findstr paramiko
   pip list | findstr fastapi
   ```
   
   Reinstall if missing:
   ```powershell
   pip install -r requirements.txt
   pip install mcp
   ```

3. **Check config files**
   ```powershell
   # Should exist and be valid YAML
   Test-Path D:\Projects\remote_terminal\config.yaml
   Test-Path D:\Projects\remote_terminal\hosts.yaml
   ```

4. **Review Python errors in logs**
   - Import errors → reinstall dependencies
   - File not found → check paths
   - YAML errors → validate syntax

### Claude Shows Error When Calling Tools

**Symptom:** Tool calls fail with errors

**Check:**

1. **Server connection**
   ```
   Ask Claude: "Check the terminal status"
   ```

2. **Logs in real-time**
   ```powershell
   # In separate PowerShell window
   Get-Content D:\Projects\remote_terminal\logs\remote_terminal.log -Wait -Tail 50
   ```

3. **Database issues**
   ```powershell
   # Check database exists and is accessible
   Test-Path D:\Projects\remote_terminal\data\remote_terminal.db
   ```

---

## Web Terminal Problems

### Web Terminal Doesn't Open

**Symptom:** Browser doesn't open automatically

**Solutions:**

1. **Manual open**
   ```
   Open browser to: http://localhost:8080
   ```

2. **Check port availability**
   ```powershell
   # See if port 8080 is in use
   netstat -ano | findstr :8080
   ```

3. **Change port if needed**
   ```yaml
   # config.yaml
   server:
     port: 8081  # Use different port
   ```

4. **Disable auto-open**
   ```yaml
   # config.yaml
   server:
     auto_open_browser: false  # Open manually
   ```

5. **Firewall blocking**
   - Check Windows Firewall
   - Allow Python through firewall
   - Allow port 8080 (or your custom port)

### Web Terminal Shows "Connection Refused"

**Symptom:** Browser opens but can't connect

**Solutions:**

1. **Verify server is running**
   ```powershell
   # Should show Python listening on port 8080
   netstat -ano | findstr :8080
   ```

2. **Check logs**
   ```powershell
   Get-Content D:\Projects\remote_terminal\logs\remote_terminal.log -Tail 100
   ```

3. **Restart MCP server**
   - Close Claude Desktop completely
   - Wait 10 seconds
   - Restart Claude Desktop

### Web Terminal Shows Blank/Empty

**Symptom:** Terminal opens but shows nothing

**Solutions:**

1. **Refresh browser** (F5 or Ctrl+R)

2. **Clear browser cache**
   - Ctrl+Shift+Delete
   - Clear cache
   - Reload page

3. **Check browser console** (F12)
   - Look for JavaScript errors
   - Look for WebSocket connection errors

4. **Try different browser**
   - Sometimes browser-specific issues
   - Test with Chrome, Firefox, or Edge

### Commands Don't Appear in Web Terminal

**Symptom:** Commands execute but don't show in terminal

**Solutions:**

1. **Refresh the page**

2. **Check SSH connection**
   ```
   Ask Claude: "Check the connection status"
   ```

3. **Verify shared connection**
   - Web terminal and MCP should share same SSH session
   - Check logs for connection info

---

## Command Execution Issues

### Commands Time Out

**Symptom:** Commands exceed timeout

**Solutions:**

1. **Increase timeout for specific command**
   ```
   Tell Claude: "Install nginx, this will take a while"
   ```
   Claude will use longer timeout automatically.

2. **Adjust default timeout**
   ```yaml
   # config.yaml
   command_execution:
     default_timeout: 30  # Increase from 10
   ```

3. **Use batch execution**
   - More efficient for long operations
   - Better progress tracking

### Command Hangs / Never Completes

**Symptom:** Command runs indefinitely

**Solutions:**

1. **Cancel the command**
   ```
   Tell Claude: "Cancel the current command"
   ```

2. **Check for interactive prompts**
   - Commands asking for input will hang
   - Use `-y` flags: `apt install -y nginx`
   - Use `--force` or `--non-interactive` options

3. **Review command in web terminal**
   - See what it's waiting for
   - May need user input

### Sudo Commands Fail

**Symptom:** Permission denied on sudo commands

**Solutions:**

1. **Verify sudo access**
   ```bash
   # On remote server
   sudo -l  # List sudo permissions
   ```

2. **Passwordless sudo (recommended)**
   ```bash
   # On remote server, edit sudoers
   sudo visudo
   
   # Add line (replace 'username')
   username ALL=(ALL) NOPASSWD: ALL
   ```

3. **Alternative: Use root user**
   ```yaml
   # hosts.yaml
   user: root
   ```

### Commands Return Incomplete Output

**Symptom:** Output appears truncated

**Solutions:**

1. **Request full output**
   ```
   Tell Claude: "Show me the complete unfiltered output"
   ```

2. **Check output mode**
   ```
   Tell Claude: "Use full output mode for this command"
   ```

3. **Review web terminal**
   - Full output always visible there
   - No filtering applied

4. **Adjust filtering thresholds**
   ```yaml
   # config.yaml
   claude:
     thresholds:
       generic: 100  # Increase from 50
   ```

---

## File Transfer Problems

### Upload Fails

**Symptom:** File upload doesn't work

**Solutions:**

1. **Check local file path**
   ```powershell
   # Verify file exists
   Test-Path "C:\path\to\file.txt"
   ```

2. **Check remote permissions**
   ```bash
   # On remote server
   ls -la /target/directory
   
   # Ensure write permissions
   ```

3. **Check disk space**
   ```bash
   # On remote server
   df -h
   ```

4. **Path format**
   - Use absolute paths
   - Windows: `C:\Users\WindowsUser\file.txt`
   - Linux: `/home/linuxuser/file.txt`

### Download Fails

**Symptom:** Cannot download from server

**Solutions:**

1. **Check remote file exists**
   ```bash
   # On remote server
   ls -la /path/to/file
   ```

2. **Check local directory writable**
   ```powershell
   # Verify directory exists and writable
   Test-Path "C:\Downloads"
   ```

3. **Check file permissions**
   ```bash
   # On remote server
   chmod 644 /path/to/file  # Make readable
   ```

### Directory Transfer Very Slow

**Symptom:** Large directory transfer takes too long

**Solutions:**

1. **Enable compression**
   ```
   Tell Claude: "Upload with compression always enabled"
   ```

2. **Exclude unnecessary files**
   ```
   Tell Claude: "Upload but exclude node_modules and .git"
   ```

3. **Check network speed**
   ```powershell
   # Test download speed
   Test-Connection 192.168.1.100 -Count 10
   ```

4. **Use background mode**
   ```
   Tell Claude: "Upload in background mode"
   ```

---

## Batch Execution Errors

### Batch Script Fails

**Symptom:** Batch execution stops with error

**Solutions:**

1. **Review error in response**
   - Claude receives error summary
   - Full log saved locally

2. **Check local log file**
   ```
   C:\Users\YOUR_USERNAME\mcp_batch_logs\batch_output_TIMESTAMP.log
   ```

3. **Test commands individually**
   - Run each command separately
   - Identify which one fails

4. **Fix script errors**
   - Add error handling: `command || echo "Failed (OK)"`
   - Remove `set -e` for non-critical errors

### Batch Progress Not Showing

**Symptom:** No progress markers in output

**Solutions:**

1. **Add step markers**
   ```bash
   echo "=== [STEP 1/3] Description ==="
   command_here
   echo "[STEP_1_COMPLETE]"
   ```

2. **Check script format**
   - Must include markers for tracking
   - Use helper tool to create proper format

### Batch Log File Not Found

**Symptom:** Log file not saved locally

**Solutions:**

1. **Check log directory exists**
   ```powershell
   Test-Path "C:\Users\$env:USERNAME\mcp_batch_logs"
   
   # Create if missing
   New-Item -ItemType Directory -Path "C:\Users\$env:USERNAME\mcp_batch_logs"
   ```

2. **Check permissions**
   - Ensure write access to directory

3. **Check disk space**
   ```powershell
   Get-PSDrive C | Select-Object Used,Free
   ```

---

## Database Issues

### Database Locked

**Symptom:** "Database is locked" error

**Solutions:**

1. **Close other connections**
   - Only one MCP server should run
   - Check Task Manager for multiple Python processes

2. **Restart MCP server**
   - Close Claude Desktop
   - Wait 10 seconds
   - Restart

3. **Check database file**
   ```powershell
   # Verify not corrupted
   python -c "import sqlite3; conn = sqlite3.connect('D:/Projects/remote_terminal/data/remote_terminal.db'); conn.execute('PRAGMA integrity_check'); conn.close(); print('OK')"
   ```

### Database Corruption

**Symptom:** Database errors on queries

**Solutions:**

1. **Backup current database**
   ```powershell
   Copy-Item "D:\Projects\remote_terminal\data\remote_terminal.db" "D:\Projects\remote_terminal\data\remote_terminal.db.backup"
   ```

2. **Try repair**
   ```powershell
   python -c "import sqlite3; conn = sqlite3.connect('D:/Projects/remote_terminal/data/remote_terminal.db'); conn.execute('VACUUM'); conn.close(); print('Vacuumed')"
   ```

3. **Restore from backup** (if available)
   ```powershell
   Copy-Item "D:\Projects\remote_terminal\data\remote_terminal.db.backup" "D:\Projects\remote_terminal\data\remote_terminal.db"
   ```

4. **Fresh start** (loses history)
   ```powershell
   Remove-Item "D:\Projects\remote_terminal\data\remote_terminal.db"
   # Database will be recreated on next start
   ```

---

## Performance Problems

### Slow Response Times

**Symptom:** Commands take long to return

**Solutions:**

1. **Network latency**
   ```powershell
   # Check ping time
   Test-Connection 192.168.1.100 -Count 10
   ```

2. **Server load**
   ```bash
   # Check server resources
   top
   free -h
   df -h
   ```

3. **Optimize output filtering**
   ```yaml
   # config.yaml - reduce thresholds
   claude:
     thresholds:
       generic: 30  # More aggressive filtering
   ```

### High Memory Usage

**Symptom:** Python process uses lots of RAM

**Solutions:**

1. **Limit command history**
   ```yaml
   # config.yaml
   command_execution:
     max_command_history: 20  # Reduce from 50
   ```

2. **Clean up old commands**
   ```yaml
   # config.yaml
   command_execution:
     cleanup_interval: 60  # More frequent cleanup
   ```

3. **Restart periodically**
   - Close Claude Desktop
   - Restart to clear memory

---

## Configuration Errors

### YAML Syntax Error

**Symptom:** Cannot load config files

**Solutions:**

1. **Validate YAML syntax**
   - Use online YAML validator
   - Check indentation (spaces, not tabs)
   - Check for special characters

2. **Common mistakes**
   ```yaml
   # WRONG - tabs used
   	server:
   		port: 8080
   
   # CORRECT - spaces used
   server:
     port: 8080
   ```

3. **Reset to defaults**
   - Restore original config.yaml from project
   - Restore original hosts.yaml

### Invalid Configuration Values

**Symptom:** Values out of range or invalid

**Solutions:**

1. **Check value ranges**
   ```yaml
   command_execution:
     default_timeout: 10      # Must be positive
     max_timeout: 3600        # Must be >= default
   ```

2. **Validate port numbers**
   ```yaml
   server:
     port: 8080  # Must be 1024-65535 for non-root
   ```

---

## Debugging Tips

### Enable Debug Logging

```yaml
# config.yaml
logging:
  level: DEBUG  # Change from INFO
```

Restart MCP server to apply.

### Monitor Logs in Real-Time

```powershell
# Watch logs live
Get-Content D:\Projects\remote_terminal\logs\remote_terminal.log -Wait -Tail 50
```

### Test Individual Components

**SSH Connection:**
```powershell
python -c "from src.ssh_manager import SSHManager; mgr = SSHManager('host', 'user', 'pass'); print(mgr.connect())"
```

**Database:**
```powershell
python view_db.py
```

**Config Loading:**
```powershell
python -c "from src.config import Config; c = Config('config.yaml'); print('Loaded OK')"
```

### Capture Network Traffic

```powershell
# Use Wireshark to capture SSH traffic
# Filter: tcp.port == 22
```

### Check Python Dependencies

```powershell
pip list
pip check
```

### Test MCP Protocol

Use standalone mode to test tools:
```powershell
.\start_standalone.ps1
```

Open: `http://localhost:8080`

---

## Getting More Help

If problems persist:

1. **Check logs**
   - Claude Desktop logs (Help → Show Logs)
   - Remote Terminal logs (logs/remote_terminal.log)

2. **Review recent changes**
   - Configuration modifications
   - Windows updates
   - Python updates

3. **Test with minimal config**
   - Use default config.yaml
   - Test with single server
   - Test simple commands first

4. **Document the issue**
   - What you were trying to do
   - What happened instead
   - Error messages
   - Logs

---

**Version:** 3.0  
**Last Updated:** December 2024
