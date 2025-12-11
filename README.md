# Remote Terminal

**AI-Powered Remote Linux Server Management via MCP**

Remote Terminal lets Claude (the AI assistant) execute commands on your remote Linux servers through a natural chat interface. Watch full output in your browser in real-time while Claude receives smart-filtered summaries optimized for token efficiency.

---

## 🎯 What Is This?

Imagine telling Claude:

```
"Install nginx on my server and configure it with SSL"
"Run complete system diagnostics and tell me if anything looks wrong"
"Find all log errors from the last hour and summarize them"
```

And Claude does it - executing commands, analyzing output, and taking action on your behalf.

**That's Remote Terminal.**

---

## ✨ Key Features

### Core Capabilities

- **🖥️ Remote Command Execution** - Run any bash command on Linux servers
- **🌐 Multi-Server Management** - Switch between multiple servers easily
- **📁 File Transfer (SFTP)** - Upload/download files and directories with compression
- **📜 Batch Script Execution** - Run multi-command scripts 10-50x faster
- **💬 Conversation Tracking** - Group commands by goal with rollback support
- **📚 Recipe System** - Save successful workflows for reuse
- **🗄️ Database Integration** - Full audit trail with SQLite
- **🌍 Interactive Web Terminal** - Full-featured terminal in browser (type, paste, scroll history)
- **🔄 Multi-Terminal Sync** - Open multiple terminals, all perfectly synchronized

### The Interactive Web Terminal

Remote Terminal provides a **fully interactive terminal window** in your browser at `http://localhost:8080` - it looks and feels just like WSL, PuTTY, or any standard terminal:

**You can:**
- Type commands directly (just like any terminal)
- Copy/paste text (Ctrl+C, Ctrl+V)
- Scroll through command history
- Use arrow keys for history navigation
- View real-time command output with colors preserved

**Claude can:**
- Execute commands that appear in your terminal
- See command results instantly
- Continue working while you watch

**The key advantage:** You maintain complete visibility and control. Every command Claude runs appears in your terminal window in real-time. You're never in the dark about what's happening on your server - it's like sitting side-by-side with an assistant who types commands for you while you watch the screen.

**Multi-Terminal Support:** Open multiple browser windows at `http://localhost:8080` - they all stay perfectly synchronized via WebSocket broadcast. Type in one terminal, see it in all terminals instantly. Perfect for multi-monitor setups or sharing your view with others.

⚠️ **Best Practice:** Close unused terminal tabs when done. While the system handles multiple connections efficiently, keeping many old tabs open can consume unnecessary resources and may cause connection issues.

#### 🎬 See It In Action

<video width="800" controls>
  <source src="https://raw.githubusercontent.com/TiM00R/remote-terminal/master/docs/demo.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video>

https://github.com/user-attachments/assets/98a6fa41-ec4f-410b-8d4a-a2422d8ac7c9

*Watch the interactive web terminal in action - see Claude execute commands while you maintain full visibility and control*

### The Dual-Stream Architecture

Behind the scenes, Remote Terminal uses a smart two-stream approach:

```
           SSH Output from Remote Server
                      ↓
                  [Raw Output]
                      ↓
                 ┌────┴────┐
                 │         │
                 ↓         ↓
             [FULL]    [FILTERED]
                 │         │
                 ↓         ↓
            Web Terminal    Claude
         (You see all)  (Smart summary)
```

**Result:**
- **You:** Full visibility and control in interactive terminal
- **Claude:** Efficient work with 95% token savings  
- **Both:** Shared SSH session, synchronized state
- **Best of both worlds!**

---

## 🚀 Quick Start

### 1. Install

**Create a folder for the project** (location doesn't matter - use any path you prefer):

Examples: `D:\Projects\remote_terminal` or `C:\MyMCPProj\remote_terminal`

**Navigate to parent folder:**
```
cd D:\Projects
```

**Clone the repository:**
```
git clone https://github.com/TiM00R/remote-terminal.git
cd remote_terminal
```

**Set up Python environment:**
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install mcp
```

### 2. Configure Your Server

Edit `hosts.yaml`:
```yaml
servers:
  - name: my-server
    host: 192.168.1.100
    user: username
    password: password
    port: 22
    default: true
```

### 3. Configure Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "remote-terminal": {
      "command": "D:\\Projects\\remote_terminal\\.venv\\Scripts\\python.exe",
      "args": ["D:\\Projects\\remote_terminal\\src\\mcp_server.py"],
      "env": {"PYTHONPATH": "D:\\Projects\\remote_terminal\\src"}
    }
  }
}
```

### 4. Restart Claude Desktop

Exit completely and restart.

### 5. Test It!

Ask Claude:
```
Execute the command 'whoami' on my server
```

**Interactive terminal opens automatically** → Type or watch commands execute → Claude responds!

------

## 📖 Documentation

Complete guides for every use case:

- **[QUICK_START.md](docs/QUICK_START.md)** - Get running in 5 minutes
- **[INSTALLATION.md](docs/INSTALLATION.md)** - Detailed setup instructions
- **[USER_GUIDE.md](docs/USER_GUIDE.md)** - Complete feature walkthrough
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Common problems and solutions
- **[WEBSOCKET_BROADCAST.md](docs/WEBSOCKET_BROADCAST.md)** - Multi-terminal synchronization details

---

## 💡 Usage Examples

### System Administration

```
"Check disk space and memory usage"
"What processes are using the most CPU?"
"Is nginx running? If not, start it"
"Show me the last 50 lines of the system log"
```

### Software Management

```
"Install htop and verify it works"
"Update all packages"
"Check if docker is installed and what version"
```

### Troubleshooting

```
"Run complete network diagnostics"
"Find all errors in the last hour of logs"
"Check why nginx won't start"
"Analyze disk usage by directory"
```

### File Operations

```
"Upload my local config.json to /etc/app/"
"Download all log files from /var/log/myapp/"
"List files in /var/log modified today"
"Find all files larger than 100MB"
```

### Automation

```
"Create a recipe from our successful nginx installation"
"Execute the network diagnostics recipe"
"Start a conversation to configure WiFi"
```

---

## 🎨 Example Session

**You:**
> Install nginx on my production server

**Claude:**
> I'll install nginx. This will create a package installation...

*Interactive terminal opens automatically at http://localhost:8080*

**Web Terminal shows (real-time):**
```
$ sudo apt install nginx
Reading package lists... Done
Building dependency tree... Done
[... 500+ lines of installation output ...]
Setting up nginx (1.18.0-0ubuntu1) ...
Created symlink /etc/systemd/system/multi-user.target.wants/nginx.service
Processing triggers for systemd (245.4-4ubuntu3.23) ...
```

**Claude receives (filtered summary):**
```
nginx installed successfully in 45s
12 packages installed
Service: nginx.service is active
```

**Claude responds:**
> nginx has been successfully installed and is now running. The service is active. Would you like me to configure it or show you the default page?

**Token savings: 96% (15,000 tokens → 600 tokens)**

---

## 🏗️ Architecture

### Project Structure

```
remote_terminal/
├── data/                      # SQLite database
│   └── remote_terminal.db     # Command history, conversations, recipes
├── docs/                      # Documentation
│   ├── QUICK_START.md
│   ├── INSTALLATION.md
│   ├── USER_GUIDE.md
│   ├── TROUBLESHOOTING.md
│   └── WEBSOCKET_BROADCAST.md
├── recipes/                   # Example automation recipes
├── src/                       # Source code
│   ├── tools/                 # MCP tool modules
│   │   ├── tools_hosts.py     # Server management
│   │   ├── tools_commands.py  # Command execution
│   │   ├── tools_sftp.py      # File transfer
│   │   ├── tools_batch.py     # Batch execution
│   │   ├── tools_conversations.py
│   │   └── tools_recipes.py
│   ├── mcp_server.py          # MCP server entry point
│   ├── ssh_manager.py         # SSH connection handling
│   ├── command_state.py       # Command tracking
│   ├── database_manager.py    # SQLite integration
│   ├── output_filter.py       # Smart filtering
│   ├── prompt_detector.py     # Command completion detection
│   └── web_terminal.py        # WebSocket-enabled web interface
├── standalone/                # Standalone web UI
├── config.yaml                # Global settings
├── hosts.yaml                 # Server configurations
└── requirements.txt           # Python dependencies
```

### Technology Stack

- **Python 3.9+** - Core language
- **MCP Protocol** - Claude integration
- **Paramiko** - SSH/SFTP library
- **NiceGUI + WebSockets** - Web terminal with multi-terminal sync
- **SQLite** - Database for history/recipes
- **FastAPI** - Web framework

---

## 🔧 Configuration

### config.yaml

Controls timeouts, filtering thresholds, web server, logging:

```yaml
connection:
  keepalive_interval: 30
  connection_timeout: 10

command_execution:
  default_timeout: 10
  max_timeout: 3600

claude:
  auto_send_errors: true
  thresholds:
    install: 100
    file_listing: 50
    generic: 50

server:
  host: localhost
  port: 8080
  auto_open_browser: true
```

### hosts.yaml

Define your servers:

```yaml
servers:
  - name: production
    host: 192.168.1.100
    user: admin
    password: secure_pass
    port: 22
    default: true
    tags: production, critical
    
  - name: development
    host: 192.168.1.101
    user: dev
    password: dev_pass
    tags: development
```

---

## 🛡️ Security Considerations

### Current Status

- Passwords stored in plain text in `hosts.yaml`
- Web terminal bound to localhost only (not network-exposed)
- Full command audit trail in database
- SSH uses standard security (password authentication)

------

## 📊 Performance

### Token Efficiency

Average token savings on verbose commands:

| Command Type | Full Output | Filtered | Savings |
|--------------|-------------|----------|---------|
| apt install  | ~15,000     | ~600     | **96%** |
| ls -la /var  | ~8,000      | ~400     | **95%** |
| Log search   | ~12,000     | ~500     | **96%** |
| find /       | ~30,000     | ~800     | **97%** |

**Average: 95-98% token reduction on verbose commands**

### Speed Improvements

Batch execution vs sequential:

- **10 commands sequential:** 5 minutes (10 round-trips)
- **10 commands batch:** 30 seconds (1 round-trip)
- **Speed improvement: 10x faster!**

---

## 🔍 Advanced Features

### Conversation Tracking

Group related commands by goal:

```
Start conversation: "Configure nginx with SSL"
→ [Execute multiple commands]
→ End conversation: success
→ Create recipe from conversation
```

Benefits:
- Organized command history
- Rollback capability
- Context for AI
- Recipe generation

### Recipe System

Save successful workflows:

```python
# Recipe: wifi_diagnostics
1. lspci | grep -i network
2. iwconfig
3. ip link show
4. dmesg | grep -i wifi
5. systemctl status NetworkManager
```

Reuse on any compatible server:
```
Execute wifi_diagnostics recipe on my new server
```

### Machine Identity

Each server tracked by unique machine_id (hardware + OS fingerprint):
- Commands tracked per physical machine
- Recipes execute on compatible systems
- Audit trail maintains integrity
- Handles server IP changes

---

## 🐛 Known Issues & Limitations

### Current Limitations

1. **Designed for Windows local machine**
   - Currently optimized for Windows 10/11
   - Linux/Mac support possible with modifications

2. **SSH Key Support not implemented**
   - Password authentication only
   - SSH keys work with manual SSH but not integrated with MCP tools

3. **Works with only one remote server at a time**
   - Can configure multiple servers
   - Can only actively work with one server per session
   - Switch between servers as needed

------

## 🤝 Contributing

This is Tim's personal project. If you'd like to contribute:

1. Test thoroughly on your setup
2. Document any issues found
3. Suggest improvements
4. Share recipes you create

---

## 📜 Version History

### Version 3.0 (Current - December 2024)

- ✅ Converted from PostgreSQL to SQLite
- ✅ Eliminated Docker dependency
- ✅ Multi-server support with server selection
- ✅ Machine identity tracking (hardware fingerprints)
- ✅ Conversation management (pause/resume)
- ✅ Recipe system for automation
- ✅ Batch script execution with progress tracking
- ✅ SFTP directory transfer with compression
- ✅ Comprehensive database integration
- ✅ Full audit trail
- ✅ WebSocket-based multi-terminal synchronization

### Version 2.0 (October 2024)

- ✅ Dual-stream architecture
- ✅ Smart output filtering
- ✅ Web terminal auto-open
- ✅ MCP integration with Claude

### Version 1.0 (Initial Release)

- ✅ Basic SSH command execution
- ✅ Simple web terminal
- ✅ PostgreSQL backend

---

## 📞 Support

For issues or questions:

1. **Check Documentation**
   - QUICK_START.md for setup
   - USER_GUIDE.md for features
   - TROUBLESHOOTING.md for problems
   - WEBSOCKET_BROADCAST.md for multi-terminal details

2. **Review Logs**
   - Claude Desktop logs (Help → Show Logs)
   - Remote Terminal logs (logs/remote_terminal.log)

3. **Test Components**
   - Use standalone mode (start_standalone.ps1)
   - Test SSH manually
   - Verify database (view_db.py)

---

## 📄 License

This project is for personal use by Tim. Not currently open source.

---

## 🙏 Acknowledgments

- **Anthropic** - Claude and MCP protocol
- **Paramiko** - SSH library
- **FastAPI** - Web framework
- **NiceGUI** - UI components with WebSocket support

---

**Ready to let Claude manage your servers? Check out [QUICK_START.md](docs/QUICK_START.md) to get started in 5 minutes!**

---

**Version:** 3.0 (SQLite-based, multi-server support, WebSocket multi-terminal sync)  
**Last Updated:** December 2024  
**Maintainer:** Tim
