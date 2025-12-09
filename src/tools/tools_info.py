"""
System Information Tools
Tools for getting status and information about the remote terminal
"""

import logging
from mcp import types

logger = logging.getLogger(__name__)


async def get_tools(**kwargs) -> list[types.Tool]:
    """Get list of information tools"""
    return [
        types.Tool(
            name="get_terminal_status",
            description="Check the connection status of the remote terminal",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


async def handle_call(name: str, arguments: dict, shared_state, config, web_server, hosts_manager, **kwargs) -> list[types.TextContent]:
    """Handle information tool calls"""
    
    if name == "get_terminal_status":
        return await _get_status(shared_state, config, web_server, hosts_manager)
    
    # Not our tool, return None
    return None


async def _get_status(shared_state, config, web_server, hosts_manager) -> list[types.TextContent]:
    """Get connection status"""
    
    current_server = hosts_manager.get_current()
    
    if shared_state.ssh_manager:
        info = shared_state.ssh_manager.get_connection_info()
        registry_stats = shared_state.command_registry.get_stats()

        status = f"""Remote Terminal Status:
- Host: {info['host']}:{info['port']}
- User: {info['user']}
- Connected: {info['connected']}
- Reconnecting: {info['reconnecting']}"""

        if current_server:
            status += f"\n- Server: {current_server.name}"
        
        status += f"""
- Web Terminal: {'Running' if web_server.is_running() else 'Not started'}
- Web URL: http://localhost:{config.server.port}

Command Tracking:
- Total commands: {registry_stats['total_commands']}
- By status: {registry_stats['by_status']}
"""
        # REMOVED: HistoryManager section (unused - bash handles history)
        
        return [types.TextContent(type="text", text=status)]
    else:
        return [types.TextContent(
            type="text",
            text="Terminal not initialized. Use select_server to connect."
        )]
