"""
Recipe Management Tools
Tools for creating and managing command recipes from successful conversations
"""

import logging
from mcp import types
from database_manager import DatabaseManager
import json
from .tools_hosts import _select_server
from .tools_conversations import _start_conversation, _end_conversation
from .decorators import requires_connection

#from .tools_commands import _execute_command
#from .tools_batch import _execute_script_content
from .tools_commands import execute_command_with_track
from .tools_batch import _execute_script_content

import sqlite3

logger = logging.getLogger(__name__)


async def get_tools(**kwargs) -> list[types.Tool]:
    """Get list of recipe management tools"""
    return [
        types.Tool(
            name="create_recipe",
            description="""Create a reusable recipe from a successful conversation.

A recipe is a documented, reusable command sequence extracted from a successful conversation.
Recipes can be executed later on any compatible server.

USAGE:
- Call after a conversation ends successfully
- Provide clear name and description
- Optionally specify prerequisites and success criteria
- Command sequence is automatically extracted from conversation

RETURNS:
- recipe_id: Use this to reference the recipe
- name: Recipe name
- command_count: Number of commands in recipe
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "integer",
                        "description": "Source conversation ID to create recipe from"
                    },
                    "name": {
                        "type": "string",
                        "description": "Short descriptive name (e.g., 'wifi_diagnostics', 'docker_install')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of what the recipe does"
                    },
                    "prerequisites": {
                        "type": "string",
                        "description": "Optional: System requirements (e.g., 'Ubuntu 22.04+, sudo access')",
                        "default": ""
                    },
                    "success_criteria": {
                        "type": "string",
                        "description": "Optional: How to verify success (e.g., 'Service running, port 8080 open')",
                        "default": ""
                    }
                },
                "required": ["conversation_id", "name", "description"]
            }
        ),
        types.Tool(
            name="list_recipes",
            description="""List all available recipes.

Useful for:
- Browsing available automation recipes
- Finding recipes for specific tasks
- Reviewing recipe history

RETURNS: List of recipes with:
- id, name, description
- command_count
- times_used, last_used_at
- created_at, created_by
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 50)",
                        "default": 50
                    }
                }
            }
        ),
        types.Tool(
            name="get_recipe",
            description="""Get detailed recipe information including command sequence.

Use this to:
- View complete recipe details
- See exact command sequence
- Check prerequisites and success criteria

RETURNS:
- Full recipe details
- Complete command sequence
- Usage statistics
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipe_id": {
                        "type": "integer",
                        "description": "Recipe ID"
                    }
                },
                "required": ["recipe_id"]
            }
        ),
        types.Tool(
            name="execute_recipe",
            description="""Execute a saved recipe on current or specified server.
Handles both shell commands and MCP tool calls automatically.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipe_id": {
                        "type": "integer",
                        "description": "Recipe ID to execute"
                    },
                    "server_identifier": {
                        "type": "string",
                        "description": "Optional: Server name/host to execute on"
                    },
                    "start_conversation": {
                        "type": "boolean",
                        "default": False,
                        "description": "Create conversation to track execution"
                    },
                    "conversation_goal": {
                        "type": "string",
                        "description": "Optional: Goal description if starting conversation"
                    }
                },
                "required": ["recipe_id"]
            }
        ),      
        types.Tool(
            name="delete_recipe",
            description="""Delete a recipe (nard delete - not recoverable).

USAGE:
- First call without confirm=true to see recipe details
- Second call with confirm=true to actually delete
- Deleted recipes are hidden but preserved in database

IMPORTANT: This requires confirmation to prevent accidental deletion.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipe_id": {
                        "type": "integer",
                        "description": "Recipe ID to delete"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Confirmation flag (set to true to proceed)",
                        "default": False
                    }
                },
                "required": ["recipe_id"]
            }
        ),
        types.Tool(
            name="create_recipe_from_commands",
            description="""Create a recipe from a command list (no conversation required).

Use this to:
- Build recipes manually without executing first
- Create recipes from documentation
- Combine commands from multiple sources

COMMAND TYPES:
1. Shell: {"sequence": 1, "command": "ls -la", "description": "List"}
2. MCP: {"sequence": 2, "type": "mcp_tool", "tool": "execute_script_content", "params": {...}}
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Recipe name (must be unique)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description"
                    },
                    "commands": {
                        "type": "array",
                        "description": "List of commands",
                        "items": {"type": "object"}
                    },
                    "prerequisites": {
                        "type": "string",
                        "description": "Optional: System requirements",
                        "default": ""
                    },
                    "success_criteria": {
                        "type": "string",
                        "description": "Optional: How to verify success",
                        "default": ""
                    }
                },
                "required": ["name", "description", "commands"]
            }
        ),
        types.Tool(
            name="update_recipe",
            description="""Update an existing recipe in-place (preserves ID and usage stats).

Allows modifying any recipe fields while keeping the same recipe ID.
Only updates fields you specify - all other fields remain unchanged.

USAGE:
- Specify recipe_id and any fields you want to update
- Fields not specified will remain unchanged
- Preserves: recipe ID, created_at, times_used, last_used_at
- Updates: any fields you provide

IMPORTANT: This modifies the recipe in-place. The old version is not saved.
If you want to keep both versions, use create_recipe_from_commands instead.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipe_id": {
                        "type": "integer",
                        "description": "Recipe ID to update"
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional: New recipe name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional: New description"
                    },
                    "commands": {
                        "type": "array",
                        "description": "Optional: New command sequence (replaces all commands)",
                        "items": {"type": "object"}
                    },
                    "prerequisites": {
                        "type": "string",
                        "description": "Optional: New prerequisites"
                    },
                    "success_criteria": {
                        "type": "string",
                        "description": "Optional: New success criteria"
                    }
                },
                "required": ["recipe_id"]
            }
        ),
    ]
    
def _convert_datetimes_to_strings(obj):
    """Recursively convert all datetime objects to strings"""
    from datetime import datetime
    
    if isinstance(obj, datetime):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: _convert_datetimes_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetimes_to_strings(item) for item in obj]
    else:
        return obj



async def handle_call(name: str, arguments: dict, shared_state, config, 
                      database: DatabaseManager, web_server=None,  
                      hosts_manager=None, **kwargs) -> list[types.TextContent]:
    """Handle recipe management tool calls"""

    if name == "create_recipe":
        return await _create_recipe(database, arguments)
    
    elif name == "list_recipes":
        return await _list_recipes(database, arguments)
    
    elif name == "get_recipe":
        return await _get_recipe(database, arguments)
    
    elif name == "execute_recipe":
        
        return await _execute_recipe(
            database=database,
            arguments=arguments,
            shared_state=shared_state,
            config=config,
            web_server=web_server,
            hosts_manager=hosts_manager
        )
    
    
    elif name == "delete_recipe":
        return await _delete_recipe(database, arguments)
    
    elif name == "create_recipe_from_commands":
        return await _create_recipe_from_commands(database, arguments)
    
   
    elif name == "update_recipe":
        return await _update_recipe(database, arguments)
    
   
    # Not our tool
    return None




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


async def _list_recipes(database: DatabaseManager, arguments: dict):
    """List all recipes"""
    import json
    
    limit = arguments.get("limit", 50)
    
    recipes = database.list_recipes(limit)
    # Convert datetimes and handle command_sequence
    for recipe in recipes:
        if recipe.get('command_sequence'):
            # Parse JSON string to object (if it's a string)
            import json as json_lib
            if isinstance(recipe['command_sequence'], str):
                recipe['command_sequence'] = json_lib.loads(recipe['command_sequence'])
            recipe['command_count'] = len(recipe['command_sequence'])
        else:
            recipe['command_count'] = 0
    
    recipes = _convert_datetimes_to_strings(recipes)
    
    result = {
        "count": len(recipes),
        "recipes": recipes
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def _get_recipe(database: DatabaseManager, arguments: dict):
    """Get detailed recipe information"""
    import json
    
    recipe_id = arguments["recipe_id"]
    
    recipe = database.get_recipe(recipe_id)
    
    if not recipe:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Recipe not found"
            }, indent=2)
        )]
    
    # Parse command_sequence JSON (if it's a string)
    if recipe.get('command_sequence'):
        import json as json_lib
        if isinstance(recipe['command_sequence'], str):
            recipe['command_sequence'] = json_lib.loads(recipe['command_sequence'])
        recipe['command_count'] = len(recipe['command_sequence'])
    else:
        recipe['command_count'] = 0
    
    # Convert datetimes
    recipe = _convert_datetimes_to_strings(recipe)
    
    return [types.TextContent(
        type="text",
        text=json.dumps(recipe, indent=2)
    )]
  



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

@requires_connection

@requires_connection
async def _execute_recipe(database, arguments, shared_state, config, web_server, hosts_manager):
    """Execute a recipe on current or specified server"""
    
    recipe_id = arguments["recipe_id"]
    server_identifier = arguments.get("server_identifier")
    start_conversation = arguments.get("start_conversation", False)
    conversation_goal = arguments.get("conversation_goal")
    
    # Get recipe
    recipe = database.get_recipe(recipe_id)
    if not recipe:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Recipe not found"}, indent=2)
        )]
    
    # Parse command sequence
    if isinstance(recipe['command_sequence'], str):
        recipe['command_sequence'] = json.loads(recipe['command_sequence'])
    
    # Switch server if specified
    if server_identifier:
        await _select_server(database, {"identifier": server_identifier}, shared_state)
    
    # Start conversation if requested
    conversation_id = None
    if start_conversation:
        goal = conversation_goal or f"Execute recipe: {recipe['name']}"
        conv_result = await _start_conversation(
            database, 
            {"goal_summary": goal},
            shared_state
        )
        conv_data = json.loads(conv_result[0].text)
        conversation_id = conv_data.get('conversation_id')
    
    results = []
    errors = []
    
    # Execute each command
    for cmd in recipe['command_sequence']:
        try:
            # Check if this is an MCP tool call
            if cmd.get('type') == 'mcp_tool':
                tool_name = cmd.get('tool')
                
                if tool_name == 'execute_script_content':
                    params = cmd.get('params', {})
                    
                    # Call in the EXACT order expected by handle_call
                    result = await _execute_script_content(
                        params.get('script_content'),      # positional arg 1
                        params.get('description'),         # positional arg 2
                        300,                               # timeout (positional arg 3)
                        params.get('output_mode', 'summary'),  # output_mode (positional arg 4)
                        shared_state,                      # positional arg 5
                        config,                            # positional arg 6
                        web_server,                        # positional arg 7
                        database,                          # positional arg 8
                        conversation_id                    # positional arg 9
                    )
                    
                    # Batch scripts return plain text (not JSON) when output_mode is 'summary'
                    if not result or len(result) == 0 or not result[0].text:
                        raise ValueError(f"Batch script returned no result")
                    
                    result_text = result[0].text
                    
                    # Parse the batch execution summary
                    import re
                    
                    # Extract batch_id (format: "batch_id=17")
                    batch_id_match = re.search(r'batch_id=(\d+)', result_text)
                    batch_id = int(batch_id_match.group(1)) if batch_id_match else None
                    
                    # Extract steps completed (format: "Steps completed: 5/5")
                    steps_match = re.search(r'Steps completed:\s+(\d+)/(\d+)', result_text)
                    steps_completed = steps_match.group(1) if steps_match else None
                    steps_total = steps_match.group(2) if steps_match else None
                    
                    # Extract execution time (format: "Execution time: 1.6s")
                    time_match = re.search(r'Execution time:\s+([\d.]+)s', result_text)
                    execution_time = time_match.group(1) if time_match else None
                    
                    # Extract status
                    status_match = re.search(r'Status:\s+(.+?)(?:\n|$)', result_text)
                    batch_status = status_match.group(1).strip() if status_match else 'completed'
                    
                    # Extract log file path (format: "Log saved to: C:\Users\...")
                    log_match = re.search(r'Log saved to:\s+(.+?)(?:\n|$)', result_text)
                    log_file = log_match.group(1).strip() if log_match else None
                    
                    results.append({
                        'sequence': cmd['sequence'],
                        'type': 'mcp_tool',
                        'tool': tool_name,
                        'status': 'completed',
                        'batch_id': batch_id,
                        'steps_completed': f"{steps_completed}/{steps_total}" if steps_completed else None,
                        'execution_time': f"{execution_time}s" if execution_time else None,
                        'batch_status': batch_status,
                        'log_file': log_file
                    })
                
                else:
                    raise ValueError(f"Unknown MCP tool: {tool_name}")     
            
            else:
                # Regular shell command
                result = await execute_command_with_track(
                    shared_state=shared_state,
                    config=config,
                    web_server=web_server,
                    command=cmd['command'],
                    timeout=10,
                    output_mode='auto',
                    database=database,
                    hosts_manager=hosts_manager,
                    conversation_id=conversation_id
                )
                                
                # Regular commands return JSON
                if not result or len(result) == 0:
                    raise ValueError(f"Command returned no result")
                
                result_text = result[0].text if result[0].text else "{}"
                result_data = json.loads(result_text)
                
                results.append({
                    'sequence': cmd['sequence'],
                    'command': cmd['command'],
                    'status': result_data.get('status'),
                    'has_errors': result_data.get('error') is not None
                })  
              
              
              
              
              
                              
        except Exception as e:
            error_msg = f"Step {cmd['sequence']} failed: {str(e)}"
            errors.append(error_msg)
            results.append({
                'sequence': cmd['sequence'],
                'status': 'failed',
                'error': str(e)
            })
    
    # End conversation if started
    if conversation_id:
        status = 'success' if not errors else 'failed'
        await _end_conversation(
            database,
            {'conversation_id': conversation_id, 'status': status},
            shared_state
        )
    
    # Update recipe usage statistics
    database.increment_recipe_usage(recipe_id)
    
    result = {
        'recipe_id': recipe_id,
        'recipe_name': recipe['name'],
        'total_steps': len(recipe['command_sequence']),
        'completed_steps': len([r for r in results if r.get('status') == 'completed']),
        'failed_steps': len(errors),
        'errors': errors,
        'results': results,
        'conversation_id': conversation_id
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]