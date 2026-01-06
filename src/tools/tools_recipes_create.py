"""
Recipe Create Operations
Functions for creating recipes from conversations or command lists
"""

import logging
import json
import sqlite3
from mcp import types
from database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


async def _create_recipe(database: DatabaseManager, arguments: dict):
    """Create a recipe from a conversation"""
    import json

    conversation_id = arguments["conversation_id"]
    name = arguments["name"]
    description = arguments["description"]
    prerequisites = arguments.get("prerequisites", "")
    success_criteria = arguments.get("success_criteria", "")

    # Get conversation details
    conversation = database.get_conversation(conversation_id)
    if not conversation:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Conversation not found"
            }, indent=2)
        )]

    # Verify conversation was successful
    if conversation['status'] != 'success':
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Can only create recipes from successful conversations (status={conversation['status']})",
                "suggestion": "End conversation with 'success' status first"
            }, indent=2)
        )]

    # Get commands from conversation
    commands = database.get_commands(conversation_id)
    if not commands:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "No commands found in conversation"
            }, indent=2)
        )]

    # # Build command sequence
    # command_sequence = []
    # for cmd in commands:
    #     command_sequence.append({
    #         "sequence": cmd['sequence_num'],
    #         "command": cmd['command_text'],
    #         "description": f"Step {cmd['sequence_num']}",
    #         "expected_success": not cmd['has_errors']
    #     })



    # Build command sequence
    command_sequence = []
    for cmd in commands:
        # Check if this is a batch script execution
        if cmd['command_text'].startswith('bash /tmp/batch_script_'):
            # Extract timestamp from filename
            import re
            match = re.search(r'batch_script_(\d{8}_\d{6})\.sh', cmd['command_text'])

            if match:
                timestamp = match.group(1)

                conn = sqlite3.connect(database.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT bs.description, bs.script_content
                    FROM batch_executions be
                    JOIN batch_scripts bs ON be.script_name = bs.name
                    WHERE be.conversation_id = ?
                    AND be.script_name LIKE ?
                    ORDER BY be.started_at DESC
                    LIMIT 1
                """, (conversation_id, f'%{timestamp}%'))

                batch_result = cursor.fetchone()
                conn.close()

                if batch_result:
                    # Store as MCP tool call
                    command_sequence.append({
                        "sequence": cmd['sequence_num'],
                        "type": "mcp_tool",
                        "tool": "execute_script_content",
                        "params": {
                            "description": batch_result[0],
                            "script_content": batch_result[1],
                            "output_mode": 'summary'
                        },
                        "expected_success": not cmd['has_errors']
                    })
                    continue

        # Regular shell command
        command_sequence.append({
            "sequence": cmd['sequence_num'],
            "command": cmd['command_text'],
            "description": f"Step {cmd['sequence_num']}",
            "expected_success": not cmd['has_errors']
        })


    # Create recipe
    recipe_id = database.create_recipe(
        name=name,
        description=description,
        command_sequence=command_sequence,
        prerequisites=prerequisites or None,
        success_criteria=success_criteria or None,
        source_conversation_id=conversation_id
    )

    if not recipe_id:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to create recipe"
            }, indent=2)
        )]

    result = {
        "recipe_id": recipe_id,
        "name": name,
        "description": description,
        "command_count": len(command_sequence),
        "source_conversation": conversation_id,
        "source_goal": conversation['goal_summary'],
        "message": f"Recipe '{name}' created successfully with {len(command_sequence)} commands"
    }

    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def _create_recipe_from_commands(database: DatabaseManager, arguments: dict):
    """Create recipe from command list"""
    import json

    name = arguments["name"]
    description = arguments["description"]
    commands = arguments["commands"]
    prerequisites = arguments.get("prerequisites", "")
    success_criteria = arguments.get("success_criteria", "")

    # Validate
    if not commands or len(commands) == 0:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Must provide at least one command"}, indent=2)
        )]

    # Process commands
    for idx, cmd in enumerate(commands):
        if 'sequence' not in cmd:
            cmd['sequence'] = idx + 1

        # Must have either 'command' or be MCP tool
        if 'command' not in cmd and cmd.get('type') != 'mcp_tool':
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Command {idx+1} missing 'command' or 'type'='mcp_tool'",
                    "command": cmd
                }, indent=2)
            )]

        if cmd.get('type') == 'mcp_tool' and 'tool' not in cmd:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": f"MCP command {idx+1} missing 'tool' field",
                    "command": cmd
                }, indent=2)
            )]

        if 'expected_success' not in cmd:
            cmd['expected_success'] = True

    # Check duplicates
    sequences = [cmd['sequence'] for cmd in commands]
    if len(sequences) != len(set(sequences)):
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Duplicate sequence numbers",
                "sequences": sequences
            }, indent=2)
        )]

    # Sort and create
    commands_sorted = sorted(commands, key=lambda x: x['sequence'])

    recipe_id = database.create_recipe(
        name=name,
        description=description,
        command_sequence=commands_sorted,
        prerequisites=prerequisites or None,
        success_criteria=success_criteria or None,
        source_conversation_id=None,
        created_by="claude"
    )

    if not recipe_id:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to create recipe (name may already exist)"
            }, indent=2)
        )]

    return [types.TextContent(
        type="text",
        text=json.dumps({
            "success": True,
            "recipe_id": recipe_id,
            "name": name,
            "command_count": len(commands_sorted),
            "message": f"Recipe '{name}' created with {len(commands_sorted)} commands",
            "note": "Test recipe with execute_recipe before using in production"
        }, indent=2)
    )]
