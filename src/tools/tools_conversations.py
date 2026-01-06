"""
Conversation Management Tools
Tools for managing command conversations and rollback tracking
Phase 1 Enhanced: Resume detection, server-scoped conversations
"""

import logging
from mcp import types
from database.database_manager import DatabaseManager
from tools.tools_conversations_lifecycle import _start_conversation, _resume_conversation, _end_conversation
from tools.tools_conversations_query import _get_conversation_commands, _list_conversations, _update_command_status

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
