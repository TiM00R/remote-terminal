"""
Recipe Modify Operations
Functions for updating and deleting recipes
"""

import logging
import json
from mcp import types
from database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


async def _delete_recipe(database: DatabaseManager, arguments: dict):
    """Delete a recipe with confirmation (hard delete)"""
    import json

    recipe_id = arguments["recipe_id"]
    confirm = arguments.get("confirm", False)

    # Get recipe
    recipe = database.get_recipe(recipe_id)
    if not recipe:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Recipe not found"}, indent=2)
        )]

    # Step 1: Show confirmation
    if not confirm:
        desc = recipe['description']
        if len(desc) > 200:
            desc = desc[:200] + "..."

        # Parse command sequence
        cmd_seq = recipe.get('command_sequence')
        if isinstance(cmd_seq, str):
            cmd_seq = json.loads(cmd_seq)
        cmd_count = len(cmd_seq) if cmd_seq else 0

        return [types.TextContent(
            type="text",
            text=json.dumps({
                "warning": "This will PERMANENTLY delete the recipe",
                "recipe_id": recipe_id,
                "recipe_name": recipe['name'],
                "recipe_description": desc,
                "command_count": cmd_count,
                "times_used": recipe['times_used'],
                "last_used": str(recipe.get('last_used_at')) if recipe.get('last_used_at') else "Never",
                "confirm_required": True,
                "instruction": "To proceed, call delete_recipe again with confirm=true"
            }, indent=2)
        )]

    # Step 2: Hard delete
    try:
        cursor = database.conn.cursor()
        cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        database.conn.commit()
        success = cursor.rowcount > 0
    except Exception as e:
        database.conn.rollback()
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Failed to delete recipe: {str(e)}"}, indent=2)
        )]

    if not success:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Recipe not found or already deleted"}, indent=2)
        )]

    return [types.TextContent(
        type="text",
        text=json.dumps({
            "success": True,
            "message": f"Recipe '{recipe['name']}' permanently deleted",
            "recipe_id": recipe_id
        }, indent=2)
    )]


async def _update_recipe(database: DatabaseManager, arguments: dict):
    """Update an existing recipe in-place"""
    import json

    recipe_id = arguments["recipe_id"]

    # Get existing recipe
    recipe = database.get_recipe(recipe_id)
    if not recipe:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Recipe not found"}, indent=2)
        )]

    # Collect updates
    updates = {}
    updated_fields = []

    # Name
    if "name" in arguments:
        updates['name'] = arguments['name']
        updated_fields.append("name")

    # Description
    if "description" in arguments:
        updates['description'] = arguments['description']
        updated_fields.append("description")

    # Prerequisites
    if "prerequisites" in arguments:
        updates['prerequisites'] = arguments['prerequisites']
        updated_fields.append("prerequisites")

    # Success criteria
    if "success_criteria" in arguments:
        updates['success_criteria'] = arguments['success_criteria']
        updated_fields.append("success_criteria")

    # Commands (validate and process)
    if "commands" in arguments:
        commands = arguments["commands"]

        # Validate
        if not commands or len(commands) == 0:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": "Commands array cannot be empty"}, indent=2)
            )]

        # Process commands (same validation as create_recipe_from_commands)
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

        # Sort and store
        commands_sorted = sorted(commands, key=lambda x: x['sequence'])
        updates['command_sequence'] = json.dumps(commands_sorted)
        updated_fields.append("commands")

    # Check if anything to update
    if not updates:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "No fields to update",
                "instruction": "Provide at least one field to update: name, description, commands, prerequisites, or success_criteria"
            }, indent=2)
        )]

    # Update recipe in database
    try:
        cursor = database.conn.cursor()

        # Build UPDATE query
        set_clauses = []
        values = []

        for field, value in updates.items():
            set_clauses.append(f"{field} = ?")
            values.append(value)

        # Add recipe_id for WHERE clause
        values.append(recipe_id)

        query = f"UPDATE recipes SET {', '.join(set_clauses)} WHERE id = ?"
        cursor.execute(query, values)
        database.conn.commit()

        # Get updated recipe
        updated_recipe = database.get_recipe(recipe_id)

        # Parse command_sequence for count
        if isinstance(updated_recipe['command_sequence'], str):
            updated_recipe['command_sequence'] = json.loads(updated_recipe['command_sequence'])

        return [types.TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "recipe_id": recipe_id,
                "recipe_name": updated_recipe['name'],
                "updated_fields": updated_fields,
                "command_count": len(updated_recipe['command_sequence']),
                "message": f"Recipe {recipe_id} updated successfully",
                "note": "Recipe ID and usage statistics preserved"
            }, indent=2)
        )]

    except Exception as e:
        database.conn.rollback()
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Failed to update recipe: {str(e)}"
            }, indent=2)
        )]
