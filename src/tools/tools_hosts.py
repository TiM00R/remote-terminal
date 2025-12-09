"""
Host/Server Management Tools
Tools for managing multiple server configurations
Phase 1 Enhanced: Conversation workflow automation
"""

import re
import time
import asyncio
# from src import shared_state
from tools.tools_commands import _execute_command
from config import Config
import logging
import json
from mcp import types

logger = logging.getLogger(__name__)


async def get_tools(**kwargs) -> list[types.Tool]:
    """Get list of host management tools"""
    return [
        types.Tool(
            name="list_servers",
            description="List all configured servers with their details",
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
            description="Set default server for auto-connect on startup",
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
                      web_server=None, **kwargs) -> list[types.TextContent]:
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

async def _list_servers(hosts_manager) -> list[types.TextContent]:
    """List all configured servers"""
    servers = hosts_manager.list_servers()
    
    if not servers:
        return [types.TextContent(
            type="text",
            text="No servers configured. Use add_server to add one."
        )]
    
    result = ["Available Servers:\n"]
    for srv in servers:
        current_marker = " [CURRENT]" if srv['is_current'] else ""
        result.append(f"• {srv['name']}{current_marker}")
        result.append(f"  Host: {srv['host']}:{srv['port']}")
        result.append(f"  User: {srv['user']}")
        if srv['description']:
            result.append(f"  Description: {srv['description']}")
        if srv['tags']:
            result.append(f"  Tags: {', '.join(srv['tags'])}")
        result.append("")
    
    return [types.TextContent(type="text", text="\n".join(result))]

async def _select_server(shared_state, hosts_manager, database, web_server, identifier: str, 
                        force_identity_check: bool = False) -> list[types.TextContent]:
    """Select and connect to a server - Phase 1 Enhanced with conversation workflow and machine_id retry logic"""
    
    # Generic pattern for internal commands
    GENERIC_PROMPT = r'^[^@\s:]+@[A-Za-z0-9.-]+:[^$#]*[$#]\s*$'
 
    srv = hosts_manager.find_server(identifier)
    
    if not srv:
        return [types.TextContent(
            type="text",
            text=f"Server not found: {identifier}. Use list_servers to see available servers."
        )]
    
    # PHASE 1: Conversation management on server switch
    if database and database.is_connected():
        # Get current machine ID
        old_machine_id = shared_state.current_machine_id

        # Pause active conversation on old machine (if any)
        if old_machine_id:
            active_conv_id = shared_state.get_active_conversation_for_server(old_machine_id)
            if active_conv_id:
                shared_state.pause_conversation(old_machine_id)
                logger.info(f"Paused conversation {active_conv_id} on old server")
    
    # Set as current
    hosts_manager.set_current(identifier)
    
    # Disconnect current connection if any
    if shared_state.is_connected():
        shared_state.ssh_manager.disconnect()

    # Connect to new server
    success = shared_state.ssh_manager.connect(
        host=srv.host,
        user=srv.user,
        password=srv.password,
        port=srv.port
    )
    
    if not success or not shared_state.ssh_manager.connect():
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Failed to connect to {identifier}"})
        )]
    
    # Wait for welcome message to fully arrive before fetching machine_id
    time.sleep(1.0)

    # ========== GET MACHINE_ID AND HOSTNAME WITH RETRY LOGIC ==========
    host = srv.host
    port = srv.port
    user = srv.user
    
    machine_id = None
    identity_status = "unknown"
    previous_machine_id = None
    hostname = ""
    machine_id_warning = None
    
    # Check cache first (unless force check requested)
    if not force_identity_check:
        cached_id = shared_state.get_cached_machine_id(host, port, user)
        # Only use cached ID if it's valid
        if cached_id and shared_state.is_valid_machine_id(cached_id):
            machine_id = cached_id
            identity_status = "cached"
            logger.info(f"Using cached machine_id: {machine_id[:16]}...")
    
    # Fetch machine_id from server if not cached or force requested
    if machine_id is None or force_identity_check:
        if force_identity_check and machine_id:
            previous_machine_id = shared_state.get_cached_machine_id(host, port, user)
        
        # Try up to 2 times to get valid machine_id
        for attempt in range(1, 3):
            try:
                logger.info(f"Fetching machine_id from server (attempt {attempt}/2)")
                
                # Use execute_command for reliable output reading
                cmd = "cat /etc/machine-id 2>/dev/null || cat /var/lib/dbus/machine-id 2>/dev/null || echo 'UNKNOWN'"
                result = await _execute_command(shared_state, shared_state.config, cmd, 5, "raw",
                                                web_server, custom_prompt_pattern=GENERIC_PROMPT)
                
                # Parse machine_id from output
                result_json = json.loads(result[0].text)
                output = result_json.get("raw_output", "")
                
                # Look for machine-id in output
                candidate_id = None
                lines = output.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    # machine-id is 32 hex characters
                    if re.match(r'^[a-f0-9]{32}$', line):
                        candidate_id = line
                        break
                
                # Validate the candidate ID
                if candidate_id and shared_state.is_valid_machine_id(candidate_id):
                    machine_id = candidate_id
                    identity_status = "verified" if not force_identity_check else "refreshed"
                    logger.info(f"Valid machine_id retrieved: {machine_id[:16]}...")
                    break  # Success! Exit retry loop
                else:
                    if candidate_id:
                        logger.warning(f"Attempt {attempt}/2: Invalid machine_id retrieved: {candidate_id}")
                    else:
                        logger.warning(f"Attempt {attempt}/2: No machine_id found in output")
                    
                    if attempt < 2:
                        # Wait before retry
                        await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Attempt {attempt}/2: Error retrieving machine_id: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        
        # After 2 attempts, check if we got valid machine_id
        if not machine_id or not shared_state.is_valid_machine_id(machine_id):
            # Create fallback ID
            machine_id = f"unknown-{host}-{int(time.time())}"
            identity_status = "unavailable"
            machine_id_warning = "Failed to retrieve valid machine_id after 2 attempts. Commands will NOT be saved to database."
            logger.error(f"Using fallback machine_id: {machine_id}")
            # DO NOT cache fallback IDs
        else:
            # Cache the valid machine_id
            shared_state.cache_machine_id(host, port, user, machine_id)
    
    # Get hostname using execute_command
    try:
        result = await _execute_command(shared_state, shared_state.config, "hostname", 5, "raw",
                                        web_server, custom_prompt_pattern=GENERIC_PROMPT)
        result_json = json.loads(result[0].text)
        output = result_json.get("raw_output", "")
        
        lines = output.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('hostname') and '@' not in line:
                hostname = line
                logger.info(f"Detected hostname: {hostname}")
                break
    except Exception as e:
        logger.error(f"Could not get hostname: {e}")
    
            
    # Update database with machine_id (only if valid)
    if database and database.is_connected():
        if shared_state.is_valid_machine_id(machine_id):
            # Returns machine_id (or None on error)
            stored_machine_id = database.get_or_create_server(
                machine_id=machine_id,
                host=host,
                user=user,
                port=port,
                hostname=hostname,
                description=srv.description or '',
                tags=', '.join(srv.tags) if srv.tags else ''
            )
        
            if stored_machine_id:
                shared_state.set_current_server(stored_machine_id)
            else:
                logger.error("Failed to store machine_id in database")
        else:
            # Fallback ID - don't save to database
            logger.warning("Skipping database save for fallback machine_id")
            shared_state.set_current_server(None)
    # ========== END ==========
     
    # Update prompt detector with new credentials
    shared_state.update_credentials(user=user, host=hostname if hostname else host)
    
    # Clear conversation mode for new server (user must choose)
    shared_state.clear_conversation_mode()
    
    # # Send newline to get fresh prompt with welcome message
    # time.sleep(0.3)
    # shared_state.ssh_manager.send_input('\n')
    # time.sleep(0.2)
    
    # Build response with open conversations and machine identity
    response_data = {
        "connected": True,
        "server_name": srv.name,
        "server_host": f"{host}:{port}",
        "user": user,
        "hostname": hostname,
        "machine_id": machine_id[:16] + "..." if len(machine_id) > 16 else machine_id,
        "identity_status": identity_status,
        "open_conversations": []
    }
    
    # Add warning if fallback ID is used
    if machine_id_warning:
        response_data["machine_id_warning"] = machine_id_warning
        response_data["database_tracking"] = "disabled"
    else:
        response_data["database_tracking"] = "enabled"
    
    # Add identity change warning if detected
    if force_identity_check and previous_machine_id and previous_machine_id != machine_id:
        response_data["identity_changed"] = True
        response_data["previous_machine_id"] = previous_machine_id[:16] + "..."
        response_data["warning"] = "Machine identity changed! This is a different physical machine."
    
    # PHASE 1: Check for conversations on new server (only if valid machine_id)
    if database and database.is_connected() and shared_state.is_valid_machine_id(machine_id):
        # Get both active and paused conversations
        active_conv = database.get_active_conversation(machine_id)
        paused_convs = database.get_paused_conversations(machine_id)
        
        # Combine into open_conversations list
        if active_conv:
            response_data["open_conversations"].append({
                "id": active_conv['id'],
                "status": "in_progress",
                "goal": active_conv['goal_summary'],
                "started_at": str(active_conv['started_at'])
            })
        
        for conv in paused_convs:
            response_data["open_conversations"].append({
                "id": conv['id'],
                "status": "paused",
                "goal": conv['goal_summary'],
                "started_at": str(conv['started_at'])
            })
    
    # Return structured response
    return [types.TextContent(
        type="text",
        text=json.dumps(response_data, indent=2)
    )]

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
