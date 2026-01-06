"""
Host/Server CRUD Operations
Add, remove, update, and query server configurations
"""

import logging
from mcp import types

logger = logging.getLogger(__name__)


async def _list_servers(hosts_manager) -> list[types.TextContent]:
    """List all configured servers with [CURRENT] and [DEFAULT] markers"""
    servers = hosts_manager.list_servers()

    if not servers:
        return [types.TextContent(
            type="text",
            text="No servers configured. Use add_server to add one."
        )]

    # Get default server name
    default_server_name = hosts_manager.default_server

    result = ["Available Servers:\n"]
    for srv in servers:
        current_marker = " [CURRENT]" if srv['is_current'] else ""
        default_marker = " [DEFAULT]" if srv['name'] == default_server_name else ""
        result.append(f"• {srv['name']}{current_marker}{default_marker}")
        result.append(f"  Host: {srv['host']}:{srv['port']}")
        result.append(f"  User: {srv['user']}")
        if srv['description']:
            result.append(f"  Description: {srv['description']}")
        if srv['tags']:
            result.append(f"  Tags: {', '.join(srv['tags'])}")
        result.append("")

    return [types.TextContent(type="text", text="\n".join(result))]


async def _add_server(hosts_manager, arguments: dict) -> list[types.TextContent]:
    """Add a new server"""
    try:
        tags_str = arguments.get('tags', '')
        tag_list = [t.strip() for t in tags_str.split(',') if t.strip()]

        server = hosts_manager.add_server(
            name=arguments['name'],
            host=arguments['host'],
            user=arguments['user'],
            password=arguments['password'],
            port=arguments.get('port', 22),
            description=arguments.get('description', ''),
            tags=tag_list
        )

        return [types.TextContent(
            type="text",
            text=f"Server '{server.name}' added successfully. Use select_server('{server.name}') to connect."
        )]

    except ValueError as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        logger.error(f"Error adding server: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Failed to add server: {e}")]


async def _remove_server(hosts_manager, identifier: str) -> list[types.TextContent]:
    """Remove a server"""
    if hosts_manager.remove_server(identifier):
        return [types.TextContent(
            type="text",
            text=f"Server '{identifier}' removed successfully"
        )]
    else:
        return [types.TextContent(
            type="text",
            text=f"Server not found: {identifier}"
        )]


async def _update_server(hosts_manager, arguments: dict) -> list[types.TextContent]:
    """Update a server configuration"""
    identifier = arguments.pop('identifier')

    # Handle tags
    if 'tags' in arguments and arguments['tags']:
        arguments['tags'] = [t.strip() for t in arguments['tags'].split(',') if t.strip()]

    # Remove None values
    updates = {k: v for k, v in arguments.items() if v is not None}

    server = hosts_manager.update_server(identifier, **updates)

    if server:
        return [types.TextContent(
            type="text",
            text=f"Server '{server.name}' updated successfully"
        )]
    else:
        return [types.TextContent(
            type="text",
            text=f"Server not found: {identifier}"
        )]


async def _get_current_server(hosts_manager) -> list[types.TextContent]:
    """Get current server info"""
    current = hosts_manager.get_current()

    if not current:
        return [types.TextContent(
            type="text",
            text="No server currently selected. Use select_server to connect."
        )]

    text = f"""Current Server: {current.name}
Host: {current.host}:{current.port}
User: {current.user}
Description: {current.description}
Tags: {', '.join(current.tags) if current.tags else 'None'}
"""

    return [types.TextContent(type="text", text=text)]


async def _set_default_server(hosts_manager, identifier: str) -> list[types.TextContent]:
    """Set default server"""
    if hosts_manager.set_default(identifier):
        return [types.TextContent(
            type="text",
            text=f"Default server set to '{identifier}'. Will auto-connect on startup."
        )]
    else:
        return [types.TextContent(
            type="text",
            text=f"Server not found: {identifier}"
        )]
