"""
Shared decorators for MCP tools
"""

import logging
import json
from functools import wraps
from mcp import types

logger = logging.getLogger(__name__)


def requires_connection(func):
    """
    Decorator that ensures connection before executing remote commands.
    Auto-connects to default server if not connected.
    
    Expects function to receive these parameters (via args/kwargs):
    - shared_state: SharedState instance
    - database: DatabaseManager instance
    - hosts_manager: HostsManager instance
    - web_server: WebTerminalServer instance (optional)
    - server_identifier: str (optional) - specific server to connect to
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract required parameters from kwargs
        shared_state = kwargs.get('shared_state')
        database = kwargs.get('database')
        hosts_manager = kwargs.get('hosts_manager')
        web_server = kwargs.get('web_server')
        server_identifier = kwargs.get('server_identifier')
        
        if not shared_state:
            raise ValueError("requires_connection: shared_state not found in function arguments")
        
        if not hosts_manager:
            raise ValueError("requires_connection: hosts_manager not found in function arguments")
        
        # Check/establish connection
        connected, error = await _ensure_connected(
            shared_state, 
            database, 
            hosts_manager, 
            web_server,
            server_identifier
        )
        
        if not connected:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": "Remote server not connected",
                    "message": error,
                    "instruction": "Connect to a server first or specify server_identifier parameter"
                }, indent=2)
            )]
        
        # Connection established, proceed with function
        return await func(*args, **kwargs)
    
    return wrapper


async def _ensure_connected(shared_state, database, hosts_manager, web_server, server_identifier=None):
    """
    Ensure we're connected to a server before executing commands.
    
    Args:
        shared_state: SharedState instance
        database: DatabaseManager instance
        hosts_manager: HostsManager instance
        web_server: WebTerminalServer instance (can be None)
        server_identifier: Optional specific server to connect to
    
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    from .tools_hosts import _select_server
    
    # Check if already connected
    if shared_state.is_connected():
        return True, None  # Already connected

    # --- 1. If a specific server is requested, connect to it ---
    if server_identifier:
        try:
            await _select_server(
                shared_state,
                hosts_manager,
                database,
                web_server,
                server_identifier,
                force_identity_check=False
            )
            return True, None
        except Exception as e:
            return False, f"Failed to connect to '{server_identifier}': {e}"

    # --- 2. No server specified: try default server from hosts_manager ---
    default_server = hosts_manager.get_default()
    if default_server:
        try:
            await _select_server(
                shared_state,
                hosts_manager,
                database,
                web_server,
                default_server.name,  # ServerHost object has .name attribute
                force_identity_check=False
            )
            return True, None
        except Exception as e:
            server_name = getattr(default_server, "name", "<unknown>")
            return False, f"Failed to auto-connect to default server '{server_name}': {e}"

    # --- 3. No default server set: return error with available servers ---
    servers = hosts_manager.list_servers()
    server_names = [s['name'] for s in servers] if servers else []
    
    if server_names:
        return (
            False,
            "Not connected to any server. Please specify 'server_identifier' parameter "
            f"or set a default server. Available servers: {', '.join(server_names)}"
        )
    else:
        return False, "Not connected to any server and no servers are configured."
