"""
Conversation Query Operations
Get commands, list conversations, and update command status
"""

import logging
from mcp import types
from database.database_manager import DatabaseManager
from datetime import datetime

logger = logging.getLogger(__name__)


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
