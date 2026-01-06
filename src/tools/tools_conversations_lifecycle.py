"""
Conversation Lifecycle Operations
Start, resume, and end conversation operations
"""

import logging
from mcp import types
from database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


def _convert_datetimes_to_strings(obj):
    """
    Recursively convert all datetime objects to strings in a data structure.
    Works with dicts, lists, and nested structures.
    """
    from datetime import datetime
    if isinstance(obj, datetime):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: _convert_datetimes_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetimes_to_strings(item) for item in obj]
    else:
        return obj


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
