"""
Command Execution Tools
Tools for executing and managing commands on remote servers
Phase 1 Enhanced: Conversation workflow automation
"""

import json
import logging
from mcp import types

# Import the shared decorator
from .decorators import requires_connection

# Import execution logic
from .tools_commands_execution import _execute_command

# Import system operations
from .tools_commands_system import (
    pre_authenticate_sudo,
    create_backup_if_needed
)

# Import status and history functions
from .tools_commands_status import (
    _check_command_status,
    _get_command_output,
    _cancel_command,
    _list_command_history,
    _list_session_commands
)

# Import database operations
from .tools_commands_database import _save_to_database

logger = logging.getLogger(__name__)


async def get_tools(**kwargs) -> list[types.Tool]:
    """Get list of command execution tools"""
    return [
        types.Tool(
            name="execute_command",
            description="""Execute command on remote Linux machine with smart completion detection.

BEHAVIOR:
- Waits for command completion (detects prompt return) OR timeout
- Returns smart-formatted output based on output_mode
- Full output stored in buffer
- Optionally tracks in conversation for rollback support

TIMEOUT:
- Default: 10 seconds (sufficient for most commands)
- Override for long operations: timeout=300 (5 min), timeout=1800 (30 min)
- Maximum: 3600 seconds (1 hour)

OUTPUT_MODE OPTIONS:
- "auto" (default): Smart output based on command type and size
  * < 100 lines: returns full output
  * >= 100 lines: returns preview only
  * Installation commands with errors: returns error contexts
  * Installation commands without errors: returns last 10 lines
- "full": Always return complete output
- "preview": First 10 + last 10 lines only
- "summary": Metadata only (line count, error flag)
- "minimal": Status + buffer_info only
- "raw": Complete unfiltered output (no truncation, no filtering)

CONVERSATION TRACKING:
- conversation_id (optional): Associate command with conversation for tracking
- If provided: command saved with conversation for rollback support
- If omitted: Behavior depends on user's conversation mode choice:
  * "in-conversation" mode: conversation_id auto-injected
  * "no-conversation" mode: command saved standalone
  * No mode set: Commands run standalone (default behavior)

⚠️ CONVERSATION MODE WORKFLOW:
- User's mode choice persists for ALL commands on current server
- Mode is set when: select_server (user chooses), start_conversation, or user explicitly sets "no-conversation"
- Mode is cleared when: switching servers, new Claude dialog
- Claude should NEVER ask before each command - the mode handles it automatically

RETURN VALUES:
- status="completed": Command finished
- status="cancelled": User interrupted with Ctrl+C
- status="timeout_still_running": Exceeded timeout, still executing
- status="backgrounded": Command backgrounded with &
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute"
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Maximum seconds to wait (default: 10, max: 3600)",
                        "default": 10
                    },
                    "output_mode": {
                        "type": "string",
                        "description": "Output format: auto, full, preview, summary, minimal, raw",
                        "enum": ["auto", "full", "preview", "summary", "minimal", "raw"],
                        "default": "auto"
                    },
                    "conversation_id": {
                        "type": "integer",
                        "description": "Optional: Associate command with conversation for tracking and rollback"
                    }
                },
                "required": ["command"]
            }
        ),
        types.Tool(
            name="check_command_status",
            description="""Check status of a long-running command.

            OUTPUT_MODE: Same options as execute_command
            - "auto": Smart decision based on output size
            - "full": Get complete output (for completed commands)
            - "preview": Peek at first/last lines
            - "summary": Just metadata (polling frequently)
            - "minimal": Status only
            - "raw": Complete unfiltered output (no truncation, no filtering)

            Use "summary" or "minimal" when polling frequently to save tokens.
            Use "full" when command completes and you need results.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "command_id": {
                        "type": "string",
                        "description": "Command ID returned by execute_command"
                    },
                    "output_mode": {
                        "type": "string",
                        "description": "Output format: auto, full, preview, summary, minimal, raw",
                        "enum": ["auto", "full", "preview", "summary", "minimal", "raw"],
                        "default": "auto"
                    }
                },
                "required": ["command_id"]
            }
        ),
        types.Tool(
            name="get_command_output",
            description="Get full unfiltered output of a command. WARNING: Uses more tokens than filtered output.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command_id": {
                        "type": "string",
                        "description": "Command ID"
                    },
                    "raw": {
                        "type": "boolean",
                        "description": "If true, returns completely unfiltered output",
                        "default": False
                    }
                },
                "required": ["command_id"]
            }
        ),
        types.Tool(
            name="cancel_command",
            description="Send Ctrl+C to a running command. Use when user wants to stop a long-running command.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command_id": {
                        "type": "string",
                        "description": "Command ID to cancel"
                    }
                },
                "required": ["command_id"]
            }
        ),
        types.Tool(
            name="list_session_commands",
            description="List tracked commands from current session with status. Shows commands in CommandRegistry (in-memory, max 50). Useful for checking what's currently running or was recently executed in this session. For historical commands from database, use list_command_history instead.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "description": "Optional: 'running', 'completed', or 'killed'",
                        "enum": ["running", "completed", "killed"]
                    }
                }
            }
        ),
        types.Tool(
            name="list_command_history",
            description="""List command execution history from database with flexible filters.

Query persistent command history across all servers and sessions. Useful for:
- Reviewing what commands were executed on a server
- Finding commands from specific dates or time periods
- Debugging by examining command history
- Auditing command execution
- Analyzing errors across multiple sessions

Returns database records with integer IDs, command text, execution status,
timestamps, error information, and conversation context when available.

By default, shows commands from the currently connected server.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "machine_id": {
                        "type": "string",
                        "description": "Filter by server machine ID (uses current server if omitted)"
                    },
                    "conversation_id": {
                        "type": "integer",
                        "description": "Filter by conversation ID"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["executed", "cancelled", "timeout", "undone"],
                        "description": "Filter by execution status"
                    },
                    "has_errors": {
                        "type": "boolean",
                        "description": "Only show commands with errors (true) or without errors (false)"
                    },
                    "after_date": {
                        "type": "string",
                        "description": "Only commands after this date (ISO format: YYYY-MM-DD)"
                    },
                    "before_date": {
                        "type": "string",
                        "description": "Only commands before this date (ISO format: YYYY-MM-DD, exclusive)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of commands to return (default: 50, max: 500)",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 500
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Skip this many commands (for pagination, default: 0)",
                        "default": 0,
                        "minimum": 0
                    },
                    "order": {
                        "type": "string",
                        "enum": ["newest_first", "oldest_first"],
                        "description": "Sort order (default: newest_first)",
                        "default": "newest_first"
                    }
                }
            }
        )
    ]



async def handle_call(name: str, arguments: dict, shared_state, config,
                      web_server, database=None,
                      hosts_manager=None, **kwargs) -> list[types.TextContent]:
    """Handle command execution tool calls - Phase 1 Enhanced"""

    if name == "execute_command":
        # Auto-inject conversation_id if user is in "in-conversation" mode
        conversation_id = arguments.get("conversation_id")
        if conversation_id is None:
            # Check if user has chosen a conversation mode
            auto_conv_id = shared_state.get_auto_conversation_id()
            if auto_conv_id is not None:
                conversation_id = auto_conv_id
                logger.debug(f"Auto-injected conversation_id: {conversation_id}")

        return await execute_command_with_track(
            shared_state=shared_state,
            config=config,
            web_server=web_server,
            command=arguments["command"],
            timeout=arguments.get("timeout", 10),
            output_mode=arguments.get("output_mode", "auto"),
            database=database,
            hosts_manager=hosts_manager,
            conversation_id=conversation_id
        )

    elif name == "check_command_status":
        return await _check_command_status(
            shared_state, config,
            arguments["command_id"],
            arguments.get("output_mode", "auto")
        )

    elif name == "get_command_output":
        return await _get_command_output(
            shared_state,
            arguments["command_id"],
            arguments.get("raw", False)
        )

    elif name == "cancel_command":
        return await _cancel_command(
            shared_state=shared_state,
            command_id=arguments["command_id"],
            database=database,
            hosts_manager=hosts_manager
        )

    elif name == "list_session_commands":
        return await _list_session_commands(
            shared_state,
            arguments.get("status_filter")
        )

    elif name == "list_command_history":
        return await _list_command_history(
            shared_state=shared_state,
            database=database,
            machine_id=arguments.get("machine_id"),
            conversation_id=arguments.get("conversation_id"),
            status=arguments.get("status"),
            has_errors=arguments.get("has_errors"),
            after_date=arguments.get("after_date"),
            before_date=arguments.get("before_date"),
            limit=arguments.get("limit", 50),
            offset=arguments.get("offset", 0),
            order=arguments.get("order", "newest_first")
        )


    # Not our tool, return None
    return None


@requires_connection
async def execute_command_with_track(*, shared_state, config, web_server, command: str, timeout: int,
                                     output_mode: str, database=None, hosts_manager=None,
                                     conversation_id=None) -> list[types.TextContent]:
    """
    HIGH-LEVEL command execution with safety features and tracking
    This is called by AI/Claude through MCP

    Features:
    - Pre-authenticates sudo (ALWAYS for ALL sudo commands)
    - Creates backups (ALWAYS for ALL file-modifying commands)
    - Executes command via basic _execute_command()
    - Saves to database with tracking info
    - Auto-injects conversation_id based on user's mode choice
    """

    # Start web server on first command if not already running
    if not web_server.is_running():
        web_server.start()

    if not shared_state.is_connected() or not shared_state.ssh_manager:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Not connected to remote machine. Use select_server to connect.",
                "status": "failed"
            })
        )]

    # Validate timeout
    max_timeout = config.command_execution.max_timeout
    if timeout > max_timeout:
        return [types.TextContent(
            type="text",
            text=f"ERROR: Timeout {timeout}s exceeds maximum {max_timeout}s"
        )]

    # Warn about long timeouts
    if timeout > config.command_execution.warn_on_long_timeout:
        logger.warning(f"Long timeout requested: {timeout}s for command: {command}")

    # PHASE 1: Pre-authenticate sudo if needed (ALWAYS, not just for conversations)
    preauth_result = await pre_authenticate_sudo(
    shared_state=shared_state,
    config=config,
    web_server=web_server,
    command=command,
    database=database,
    hosts_manager=hosts_manager
)


    # PHASE 1: Create backup if needed (ALWAYS, not just for conversations)
    backup_result = await create_backup_if_needed(shared_state, config, web_server, command)

    # Execute the actual command using basic internal function
    result_content = await _execute_command(shared_state, config, command, timeout,
                                            output_mode, web_server)

    # Parse result to add tracking info
    result = json.loads(result_content[0].text)

    # PHASE 1: Save to database if connected
    if database and database.is_connected():
        await _save_to_database(
            database, shared_state, command,
            result.get("output", result.get("raw_output", "")),
            result.get("status", "completed"),
            conversation_id, preauth_result, backup_result, result
        )

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
