"""
Recipe Management Tools
Tools for creating and managing command recipes from successful conversations
"""

import logging
from mcp import types
from database.database_manager import DatabaseManager

# Import CRUD operations
from .tools_recipes_crud import (
    _create_recipe,
    _list_recipes,
    _get_recipe,
    _delete_recipe,
    _create_recipe_from_commands,
    _update_recipe
)

# Import execution
from .tools_recipes_execution import _execute_recipe

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
