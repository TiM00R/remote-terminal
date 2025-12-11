"""
MCP Server for Remote Terminal - MODULAR VERSION (FIXED)
Exposes remote terminal capabilities to Claude via MCP with:
- Modular tool organization  
- Multi-server support
- Smart command tracking with unique IDs
- Intelligent prompt detection
- Flexible timeout handling
- Command history & rollback (Phase 1)
CLEANED: Removed unused HistoryManager references
"""

import asyncio
import sys
import logging
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# CRITICAL: Redirect ALL stdout to stderr BEFORE importing nicegui
_original_stdout = sys.stdout
sys.stdout = sys.stderr

# CRITICAL: Configure logging to stderr ONLY (not stdout)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True
)

logger = logging.getLogger(__name__)

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Add project root to path so imports work
sys.path.insert(0, str(SCRIPT_DIR))

from config import Config
from hosts_manager import HostsManager
from shared_state import _shared_state
from web_terminal import WebTerminalServer

# Import tool modules
from tools import TOOL_MODULES

# Restore stdout for MCP JSON-RPC
sys.stdout = _original_stdout


class RemoteTerminalMCP:
    """MCP Server for Remote Terminal - Modular Version"""
    
    def __init__(self):
        # Get the singleton shared state instance
        self._shared_state = _shared_state
        
        # Load config from project root
        config_path = PROJECT_ROOT / "config.yaml"
        self.config = Config(str(config_path))
        
        # Load hosts manager
        hosts_path = PROJECT_ROOT / "hosts.yaml"
        self.hosts_manager = HostsManager(str(hosts_path))
        
        # Initialize shared state (includes database initialization)
        self._shared_state.initialize(self.config)
        
        # Initialize web terminal server (pass hosts_manager for connection display)
        self.web_server = WebTerminalServer(self._shared_state, self.config, self.hosts_manager)
        
        # Web server will start on first server connection
        # self.web_server.start()  # Removed - don't auto-open
        
        self.server = Server("remote-terminal")
        self.connected = False
        
        # Store tool handlers from modules
        self.tool_handlers = {}
        
        # Register all tool modules and setup MCP handlers
        self._register_tool_modules()
        self._setup_mcp_handlers()
    
    def _register_tool_modules(self):
        """Register all tool modules and collect their handlers"""
        
        # Prepare common dependencies (includes database for Phase 1)
        # REMOVED: 'history_manager' (unused - bash handles history)
        dependencies = {
            'hosts_manager': self.hosts_manager,
            'ssh_manager': self._shared_state.ssh_manager,
            'shared_state': self._shared_state,
            'command_state': self._shared_state.command_registry,
            'database': self._shared_state.database,  # Phase 1: Database manager
            'config': self.config,
            'web_server': self.web_server
        }
        
        # Collect handlers from each tool module
        for tool_module in TOOL_MODULES:
            if hasattr(tool_module, 'get_tools') and hasattr(tool_module, 'handle_call'):
                try:
                    module_name = tool_module.__name__
                    self.tool_handlers[module_name] = {
                        'get_tools': tool_module.get_tools,
                        'handle_call': tool_module.handle_call,
                        'dependencies': dependencies
                    }
                    logger.info(f"Loaded tools from {module_name}")
                except Exception as e:
                    logger.error(f"Failed to load {tool_module.__name__}: {e}", exc_info=True)
    
    def _setup_mcp_handlers(self):
        """Setup single MCP handlers that aggregate all tool modules"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """Aggregate tools from all modules"""
            all_tools = []
            for module_name, handler in self.tool_handlers.items():
                try:
                    tools = await handler['get_tools'](**handler['dependencies'])
                    all_tools.extend(tools)
                except Exception as e:
                    logger.error(f"Error getting tools from {module_name}: {e}", exc_info=True)
            return all_tools
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            """Route tool calls to appropriate module"""
            for module_name, handler in self.tool_handlers.items():
                try:
                    result = await handler['handle_call'](name, arguments, **handler['dependencies'])
                    if result is not None:
                        return result
                except Exception as e:
                    logger.error(f"Error calling tool {name} in {module_name}: {e}", exc_info=True)
                    raise
            
            # No handler found
            raise ValueError(f"Unknown tool: {name}")
    
    def get_connection_display(self) -> str:
        """Get current connection info for display"""
        current_server = self.hosts_manager.get_current()
        if current_server and self._shared_state.is_connected():
            return f"{current_server.user}@{current_server.host} ({current_server.name})"
        elif current_server:
            return f"{current_server.name} (disconnected)"
        else:
            return "No server selected"
    
    async def initialize(self):
        """Initialize SSH connection"""
        # Just log that we're ready
        logger.info("Remote Terminal MCP initialized. Ready to handle tool calls.")
        
    
    async def cleanup(self):
        """Cleanup on shutdown"""
        # REMOVED: HistoryManager save on exit (unused - bash handles history)
        
        if self._shared_state.database:
            self._shared_state.database.disconnect()
        
        if self._shared_state.ssh_manager:
            self._shared_state.ssh_manager.disconnect()
    
    async def run(self):
        """Run the MCP server"""
        await self.initialize()
        
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options()
                )
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    mcp = RemoteTerminalMCP()
    await mcp.run()


if __name__ == "__main__":
    asyncio.run(main())
