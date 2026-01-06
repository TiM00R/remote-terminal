"""
Command Status and History - Status checking and history queries
Functions for checking command status, getting output, cancelling, and querying history
"""

import asyncio
import json
import logging
from datetime import datetime
from mcp import types
from output.output_formatter import format_output
from .decorators import requires_connection

logger = logging.getLogger(__name__)


async def _check_command_status(shared_state, config, command_id: str, output_mode: str) -> list[types.TextContent]:
    """Check status of a command"""
    state = shared_state.command_registry.get(command_id)

    if not state:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Command ID not found"}, indent=2)
        )]

    if state.is_completed():
        output = shared_state.buffer.buffer.get_text(
            start=state.buffer_start_line,
            end=state.buffer_end_line
        )

        output_data = format_output(
            command=state.command,
            output=output,
            status=state.status,
            output_mode=output_mode,
            config=config
        )

        result = {
            "command_id": command_id,
            "status": state.status,
            "duration": state.duration(),
            **output_data
        }
    else:
        result = {
            "command_id": command_id,
            "status": state.status,
            "duration": state.duration(),
            "message": "Command still executing"
        }

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_command_output(shared_state, command_id: str, raw: bool) -> list[types.TextContent]:
    """Get command output (filtered or raw)"""
    state = shared_state.command_registry.get(command_id)

    if not state:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Command ID not found"}, indent=2)
        )]

    end_line = state.buffer_end_line if state.is_completed() else None
    output = shared_state.buffer.buffer.get_text(
        start=state.buffer_start_line,
        end=end_line
    )

    if raw:
        result = {
            "command_id": command_id,
            "raw_output": output,
            "line_count": output.count('\n'),
            "size_kb": len(output) / 1024
        }
    else:
        filtered = shared_state.filter.filter_output(state.command, output)
        result = {
            "command_id": command_id,
            "filtered_output": filtered
        }

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


@requires_connection
async def _cancel_command(shared_state, command_id: str,
                          database=None,  hosts_manager=None) -> list[types.TextContent]:
    """Cancel a running command"""
    state = shared_state.command_registry.get(command_id)

    if not state:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Command ID not found"}, indent=2)
        )]

    if not state.is_running():
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Command not running (status: {state.status})"}, indent=2)
        )]

    shared_state.ssh_manager.send_interrupt()
    await asyncio.sleep(0.5)

    buffer_end_line = len(shared_state.buffer.buffer.lines)
    state.mark_killed(buffer_end_line)

    result = {
        "command_id": command_id,
        "action": "cancelled",
        "message": "Sent Ctrl+C signal to command"
    }

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def _list_command_history(shared_state, database, machine_id: str = None,
                                conversation_id: int = None, status: str = None,
                                has_errors: bool = None, after_date: str = None,
                                before_date: str = None, limit: int = 50,
                                offset: int = 0, order: str = "newest_first") -> list[types.TextContent]:
    """List command history from database with filters"""

    # Check database connection
    if not database or not database.is_connected():
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Database not connected. Command history unavailable."
            }, indent=2)
        )]

    # Determine machine_id
    if machine_id is None:
        machine_id = shared_state.current_machine_id
        if not machine_id:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": "No server specified. Either connect to a server or provide machine_id parameter."
                }, indent=2)
            )]

    # Validate date formats
    if after_date:
        try:
            datetime.fromisoformat(after_date)
        except ValueError:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Invalid after_date format: '{after_date}'. Use YYYY-MM-DD (e.g., 2024-12-01)"
                }, indent=2)
            )]

    if before_date:
        try:
            datetime.fromisoformat(before_date)
        except ValueError:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Invalid before_date format: '{before_date}'. Use YYYY-MM-DD (e.g., 2024-12-02)"
                }, indent=2)
            )]

    # Validate limit
    if limit > 500:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Limit {limit} exceeds maximum allowed (500)"
            }, indent=2)
        )]

    # Build query
    query = """
        SELECT
            c.id,
            c.command_text,
            c.status,
            c.has_errors,
            c.error_context,
            c.line_count,
            c.executed_at,
            c.conversation_id,
            c.backup_file_path,
            c.sequence_num,
            conv.goal_summary as conversation_goal
        FROM commands c
        LEFT JOIN conversations conv ON c.conversation_id = conv.id
        WHERE 1=1
    """

    params = []

    # Apply filters
    if machine_id:
        query += " AND c.machine_id = ?"
        params.append(machine_id)

    if conversation_id is not None:
        query += " AND c.conversation_id = ?"
        params.append(conversation_id)

    if status:
        query += " AND c.status = ?"
        params.append(status)

    if has_errors is not None:
        query += " AND c.has_errors = ?"
        params.append(1 if has_errors else 0)

    if after_date:
        query += " AND DATE(c.executed_at) >= DATE(?)"
        params.append(after_date)

    if before_date:
        query += " AND DATE(c.executed_at) < DATE(?)"
        params.append(before_date)

    # Order
    order_clause = "DESC" if order == "newest_first" else "ASC"
    query += f" ORDER BY c.executed_at {order_clause}"

    # Pagination
    query += f" LIMIT {limit} OFFSET {offset}"

    # Execute query
    try:
        cursor = database.conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()

        # Convert to list of dicts
        commands = []
        for row in results:
            cmd = dict(row)
            # Format executed_at as ISO string if it's a datetime
            if cmd.get('executed_at'):
                if isinstance(cmd['executed_at'], datetime):
                    cmd['executed_at'] = cmd['executed_at'].isoformat()
            commands.append(cmd)

        # Build response
        response = {
            "commands": commands,
            "metadata": {
                "total_returned": len(commands),
                "limit": limit,
                "offset": offset,
                "has_more": len(commands) == limit,
                "filters_applied": {
                    "machine_id": machine_id[:16] + "..." if machine_id and len(machine_id) > 16 else machine_id,
                    "conversation_id": conversation_id,
                    "status": status,
                    "has_errors": has_errors,
                    "after_date": after_date,
                    "before_date": before_date
                },
                "order": order
            }
        }

        return [types.TextContent(type="text", text=json.dumps(response, indent=2))]

    except Exception as e:
        logger.error(f"Error querying command history: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Database query failed: {str(e)}"
            }, indent=2)
        )]


async def _list_session_commands(shared_state, status_filter: str = None) -> list[types.TextContent]:
    """List tracked commands from current session (in-memory CommandRegistry)"""
    if status_filter:
        commands = shared_state.command_registry.get_by_status(status_filter)
    else:
        commands = shared_state.command_registry.get_all()

    result = {
        "commands": [
            {
                "command_id": cmd.command_id,
                "command": cmd.command,
                "status": cmd.status,
                "duration": cmd.duration()
            }
            for cmd in commands
        ]
    }

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
