"""
Conversation Management Tools
Tools for managing command conversations and rollback tracking
Phase 1 Enhanced: Resume detection, server-scoped conversations
"""

import logging
from datetime import datetime
from mcp import types
from database_manager import DatabaseManager

logger = logging.getLogger(__name__)


async def get_tools(**kwargs) -> list[types.Tool]:
    """Get list of conversation management tools"""
    return [
        types.Tool(
            name="start_conversation",
            description="""Start a new command conversation to track related commands.
            
A conversation groups commands by goal (e.g., "configure wifi", "install docker").
This enables rollback of entire workflows and recipe creation from successful sequences.

IMPORTANT - ACTIVE CONVERSATION DETECTION:
- If conversation already in progress on this server, returns warning
- Use force=true to create new conversation anyway
- Otherwise, resume existing conversation or end it first

USAGE:
- Start conversation before executing related commands
- All subsequent execute_command calls with conversation_id use this conversation
- End conversation when goal is achieved or abandoned

RETURNS:
- conversation_id: Use this ID for execute_command calls
- machine_id: Database ID (hardware/OS specific) of the server
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal_summary": {
                        "type": "string",
                        "description": "Brief description of what you're trying to accomplish (e.g., 'configure wifi', 'install docker')"
                    },
                    "server_identifier": {
                        "type": "string",
                        "description": "Server host or identifier (uses currently connected server if not specified)",
                        "default": ""
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force create new conversation even if one is in-progress",
                        "default": False
                    }
                },
                "required": ["goal_summary"]
            }
        ),
        types.Tool(
            name="resume_conversation",
            description="""Resume a paused conversation.

Use this when:
- New Claude dialog started and previous conversation still in progress
- Switched back to server with paused conversation
- Want to continue previous work

RETURNS:
- conversation_id: Resumed conversation ID
- goal: Original goal summary
- message: Confirmation message
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "integer",
                        "description": "Conversation ID to resume"
                    }
                },
                "required": ["conversation_id"]
            }
        ),
        types.Tool(
            name="end_conversation",
            description="""End a conversation and mark its final status.

STATUS OPTIONS:
- 'success': Goal achieved successfully
- 'failed': Goal not achieved
- 'rolled_back': Commands were undone

IMPORTANT: Status should be determined by USER feedback, not just command exit codes.
A command can succeed technically but fail to achieve the user's goal.

USAGE:
- Call after user confirms goal is achieved or failed
- Optionally add user_notes for context
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "integer",
                        "description": "Conversation ID from start_conversation"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["success", "failed", "rolled_back"],
                        "description": "Final status based on user feedback"
                    },
                    "user_notes": {
                        "type": "string",
                        "description": "Optional notes about outcome",
                        "default": ""
                    }
                },
                "required": ["conversation_id", "status"]
            }
        ),
        types.Tool(
            name="get_conversation_commands",
            description="""Get all commands from a conversation.

USAGE FOR ROLLBACK:
- Set reverse_order=true to get commands in undo sequence
- Check has_errors and backup_file_path fields
- Use this data to generate undo commands

RETURNS: Array of command objects with:
- id, sequence_num: Identification
- command_text: Original command
- result_output: Command output
- has_errors: Boolean from output analysis
- error_context: Error details if has_errors=true
- backup_file_path: Backup location if file was modified
- status: 'executed' or 'undone'
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "integer",
                        "description": "Conversation ID"
                    },
                    "reverse_order": {
                        "type": "boolean",
                        "description": "Return in reverse order (for rollback)",
                        "default": False
                    }
                },
                "required": ["conversation_id"]
            }
        ),
        types.Tool(
            name="list_conversations",
            description="""List conversations with optional filters.

Useful for:
- Finding previous work on similar goals
- Reviewing conversation history
- Identifying successful patterns for recipes

FILTERS:
- server_identifier: Limit to specific server
- status: Filter by 'in_progress', 'paused', 'success', 'failed', 'rolled_back'
- limit: Max number to return (default 50)
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_identifier": {
                        "type": "string",
                        "description": "Filter by server (optional)"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["in_progress", "paused", "success", "failed", "rolled_back"],
                        "description": "Filter by status (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 50)",
                        "default": 50
                    }
                }
            }
        ),
        types.Tool(
            name="update_command_status",
            description="""Update command status (for rollback tracking).

Call this after undoing a command to mark it as 'undone'.
This prevents re-attempting undo on already undone commands.

USAGE:
- Execute undo command via SSH
- If successful, call update_command_status(command_id, 'undone')
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "command_id": {
                        "type": "integer",
                        "description": "Command ID from get_conversation_commands"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["undone"],
                        "description": "New status (currently only 'undone' supported)"
                    }
                },
                "required": ["command_id", "status"]
            }
        )
    ]


def _convert_datetimes_to_strings(obj):
    """
    Recursively convert all datetime objects to strings in a data structure.
    Works with dicts, lists, and nested structures.
    """
    if isinstance(obj, datetime):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: _convert_datetimes_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetimes_to_strings(item) for item in obj]
    else:
        return obj


async def handle_call(name: str, arguments: dict, shared_state, config, 
                      database: DatabaseManager, hosts_manager=None, 
                      **kwargs) -> list[types.TextContent]:
    """Handle conversation management tool calls - Phase 1 Enhanced"""
    
    if name == "start_conversation":
        return await _start_conversation(shared_state, config, database, arguments)
    
    elif name == "resume_conversation":
        return await _resume_conversation(shared_state, database, arguments)
    
    elif name == "end_conversation":
        return await _end_conversation(shared_state, database, arguments)
    
    elif name == "get_conversation_commands":
        return await _get_conversation_commands(database, arguments)
    
    elif name == "list_conversations":
        return await _list_conversations(database, arguments)
    
    elif name == "update_command_status":
        return await _update_command_status(database, arguments)
    
    # Not our tool
    return None


async def _start_conversation(shared_state, config, database: DatabaseManager, arguments: dict):
    """Start a new conversation - Phase 1 Enhanced with active conversation detection"""
    import json
    
    goal_summary = arguments["goal_summary"]
    server_identifier = arguments.get("server_identifier", "")
    force = arguments.get("force", False)
    
    # Get current server info
    if not shared_state.is_connected() or not shared_state.ssh_manager:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Not connected to remote machine. Use select_server to connect first."
            }, indent=2)
        )]
    
    # Use provided identifier or current connection
    if server_identifier:
        if '@' in server_identifier:
            user, host = server_identifier.split('@', 1)
        else:
            host = server_identifier
            user = shared_state.ssh_manager.user
    else:
        host = shared_state.ssh_manager.host
        user = shared_state.ssh_manager.user
    
    port = shared_state.ssh_manager.port
    
    # Get machine_id from shared state (set by select_server)
    machine_id = shared_state.current_machine_id
    
    if not machine_id:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Not connected to server. Use select_server first."
            }, indent=2)
        )]
    
    # PHASE 1: Check for active conversation
    if not force:
        active_conv = database.get_active_conversation(machine_id)
        if active_conv:
            # Convert datetimes before returning
            active_conv = _convert_datetimes_to_strings(active_conv)
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "warning": "Active conversation found",
                    "active_conversation": {
                        "id": active_conv['id'],
                        "goal": active_conv['goal_summary'],
                        "started_at": active_conv['started_at']
                    },
                    "options": [
                        f"Resume: Use conversation_id={active_conv['id']} in execute_command",
                        f"Or call: resume_conversation({active_conv['id']})",
                        f"End old: Call end_conversation({active_conv['id']}, 'failed')",
                        "Create new: Call start_conversation with force=true"
                    ],
                    "message": f"Conversation {active_conv['id']} is still in progress. Choose an option above."
                }, indent=2)
            )]
    
    # Start conversation
    conversation_id = database.start_conversation(machine_id, goal_summary)
    
    if not conversation_id:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to start conversation"
            }, indent=2)
        )]
    
    # PHASE 1: Track in shared state
    shared_state.set_active_conversation(machine_id, conversation_id)

    result = {
        "conversation_id": conversation_id,
        "machine_id": machine_id,
        "goal": goal_summary,
        "server": f"{user}@{host}:{port}",
        "message": "Conversation started. Use conversation_id in execute_command calls."
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def _resume_conversation(shared_state, database: DatabaseManager, arguments: dict):
    """Resume a paused conversation - Phase 1 New Tool"""
    import json
    
    conversation_id = arguments["conversation_id"]
    
    # Get conversation details
    conv = database.get_conversation(conversation_id)
    if not conv:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Conversation not found"}, indent=2)
        )]
    
    # Verify status
    if conv['status'] not in ('paused', 'in_progress'):
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Cannot resume conversation with status: {conv['status']}",
                "current_status": conv['status'],
                "message": "Only 'paused' or 'in_progress' conversations can be resumed"
            }, indent=2)
        )]
    
    # Resume in database (sets status to 'in_progress')
    if not database.resume_conversation(conversation_id):
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to resume conversation in database"
            }, indent=2)
        )]
    
    # Update shared state
    machine_id = conv['machine_id']
    shared_state.set_active_conversation(machine_id, conversation_id)
    
    # Get command count
    commands = database.get_commands(conversation_id)
    
    # Convert datetimes
    conv = _convert_datetimes_to_strings(conv)
    
    return [types.TextContent(
        type="text",
        text=json.dumps({
            "conversation_id": conversation_id,
            "machine_id": machine_id,
            "goal": conv['goal_summary'],
            "started_at": conv['started_at'],
            "commands_count": len(commands),
            "message": f"Resumed conversation {conversation_id}. Use this conversation_id in execute_command."
        }, indent=2)
    )]


async def _end_conversation(shared_state, database: DatabaseManager, arguments: dict):
    """End a conversation"""
    import json
    
    conversation_id = arguments["conversation_id"]
    status = arguments["status"]
    user_notes = arguments.get("user_notes", "")
    
    success = database.end_conversation(conversation_id, status, user_notes or None)
    
    if not success:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to end conversation"
            }, indent=2)
        )]
     
    # PHASE 1: Clear from shared state if it was active
    conv = database.get_conversation(conversation_id)
    if conv:
        machine_id = conv['machine_id']
        if shared_state.get_active_conversation_for_server(machine_id) == conversation_id:
            shared_state.clear_active_conversation(machine_id)
    
    result = {
        "conversation_id": conversation_id,
        "status": status,
        "message": f"Conversation ended with status: {status}"
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def _get_conversation_commands(database: DatabaseManager, arguments: dict):
    """Get commands from a conversation"""
    import json
    
    conversation_id = arguments["conversation_id"]
    reverse_order = arguments.get("reverse_order", False)
    
    commands = database.get_commands(conversation_id, reverse_order)
    
    # Convert ALL datetime objects to strings recursively
    commands = _convert_datetimes_to_strings(commands)
    
    result = {
        "conversation_id": conversation_id,
        "command_count": len(commands),
        "reverse_order": reverse_order,
        "commands": commands
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def _list_conversations(database: DatabaseManager, arguments: dict):
    """List conversations"""
    import json
    
    server_identifier = arguments.get("server_identifier")
    status = arguments.get("status")
    limit = arguments.get("limit", 50)
    
    # For now, ignore server_identifier filter (would need to query servers table first)
    machine_id = None

    conversations = database.list_conversations(machine_id, status, limit)

    # Convert ALL datetime objects to strings recursively
    conversations = _convert_datetimes_to_strings(conversations)
    
    result = {
        "count": len(conversations),
        "conversations": conversations
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def _update_command_status(database: DatabaseManager, arguments: dict):
    """Update command status"""
    import json
    
    command_id = arguments["command_id"]
    status = arguments["status"]
    
    success = database.update_command_status(command_id, status)
    
    if not success:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to update command status"
            }, indent=2)
        )]
    
    result = {
        "command_id": command_id,
        "status": status,
        "message": f"Command status updated to: {status}"
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]
