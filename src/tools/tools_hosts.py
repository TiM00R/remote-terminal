"""
Host/Server Management Tools
Tools for managing multiple server configurations
Phase 1 Enhanced: Conversation workflow automation
"""

import logging
from mcp import types
from tools.tools_hosts_crud import (
    _list_servers,
    _add_server,
    _remove_server,
    _update_server,
    _get_current_server,
    _set_default_server
)
from tools.tools_hosts_select import _select_server

logger = logging.getLogger(__name__)


async def get_tools(**kwargs) -> list[types.Tool]:
    """Get list of host management tools"""
    return [
        types.Tool(
            name="list_servers",
            description="""List all configured servers with their details.
Shows server status markers:
- [CURRENT]: Currently connected server
- [DEFAULT]: Default server (auto-connects when no server specified)

Returns: Server names, hosts, ports, users, descriptions, tags, and status markers.
""",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="select_server",
            description="""Select and connect to a server by name, IP, or tag.

⚠️ CRITICAL CLAUDE WORKFLOW:
When this tool returns 'open_conversations' in the response, Claude MUST:
1. STOP and present the information to the user
2. ASK the user to choose ONE of these options:
   - Resume specific conversation: "resume conversation [ID]"
   - Start new conversation: "start new conversation for [goal]"
   - Run without conversation: "run commands without conversation"
3. Wait for user's explicit choice
4. Execute the choice (start_conversation, resume_conversation, or set no-conversation mode)
5. After user choice, ALL subsequent commands follow that mode (no repeated asking)

The user's choice persists for ALL commands on this server until:
- Server is switched
- New Claude dialog starts
- User explicitly changes (ends conversation, starts new, etc)

MACHINE IDENTITY:
- force_identity_check=False (default): Uses cached machine_id (fast)
- force_identity_check=True: Always re-reads machine_id from server

Use force_identity_check=True when:
- User mentions: "swapped hardware", "different box", "new machine", "verify identity"
- Physical hardware changed at same IP
- Setting up multiple boxes on same IP address
- Before critical operations requiring identity confirmation

NEVER execute commands without first getting user's choice when open_conversations exist.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Server name, host IP, or tag"
                    },
                    "force_identity_check": {
                        "type": "boolean",
                        "description": "Force re-read machine_id even if cached (default: False)",
                        "default": False
                    }
                },
                "required": ["identifier"]
            }
        ),
        types.Tool(
            name="add_server",
            description="Add a new server configuration",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Friendly name for the server"
                    },
                    "host": {
                        "type": "string",
                        "description": "IP address or hostname"
                    },
                    "user": {
                        "type": "string",
                        "description": "SSH username"
                    },
                    "password": {
                        "type": "string",
                        "description": "SSH password"
                    },
                    "port": {
                        "type": "number",
                        "description": "SSH port (default: 22)",
                        "default": 22
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description",
                        "default": ""
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tags (e.g., 'production,critical')",
                        "default": ""
                    }
                },
                "required": ["name", "host", "user", "password"]
            }
        ),
        types.Tool(
            name="remove_server",
            description="Remove a server configuration",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Server name or host to remove"
                    }
                },
                "required": ["identifier"]
            }
        ),
        types.Tool(
            name="update_server",
            description="Update an existing server configuration",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Current server name or host"
                    },
                    "name": {
                        "type": "string",
                        "description": "New name (optional)"
                    },
                    "host": {
                        "type": "string",
                        "description": "New host (optional)"
                    },
                    "user": {
                        "type": "string",
                        "description": "New user (optional)"
                    },
                    "password": {
                        "type": "string",
                        "description": "New password (optional)"
                    },
                    "port": {
                        "type": "number",
                        "description": "New port (optional)"
                    },
                    "description": {
                        "type": "string",
                        "description": "New description (optional)"
                    },
                    "tags": {
                        "type": "string",
                        "description": "New comma-separated tags (optional)"
                    }
                },
                "required": ["identifier"]
            }
        ),
        types.Tool(
            name="get_current_server",
            description="Get the currently connected server information",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="set_default_server",
            description="""Set default server (shown in list_servers with [DEFAULT] marker).

The default server is the preferred server for operations that don't specify a server.
When you execute commands without an active connection, Claude will automatically
connect to the default server.

Note: Use list_servers to see which server is currently marked as default.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Server name or host to set as default"
                    }
                },
                "required": ["identifier"]
            }
        )
    ]

async def handle_call(name: str, arguments: dict, hosts_manager, ssh_manager,
                      shared_state, database=None,
                      web_server=None,  **kwargs) -> list[types.TextContent]:
    """Handle host management tool calls - Phase 1 Enhanced"""

    if name == "list_servers":
        return await _list_servers(hosts_manager)

    elif name == "select_server":
        return await _select_server(
            shared_state, hosts_manager, database, web_server,
            arguments["identifier"],
            arguments.get("force_identity_check", False)
        )

    elif name == "add_server":
        return await _add_server(hosts_manager, arguments)

    elif name == "remove_server":
        return await _remove_server(hosts_manager, arguments["identifier"])

    elif name == "update_server":
        return await _update_server(hosts_manager, arguments)

    elif name == "get_current_server":
        return await _get_current_server(hosts_manager)

    elif name == "set_default_server":
        return await _set_default_server(hosts_manager, arguments["identifier"])

    # Not our tool, return None to let other handlers try
    return None
