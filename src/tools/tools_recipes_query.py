"""
Recipe Query Operations
Functions for listing and retrieving recipe information
"""

import logging
import json
from mcp import types
from database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


async def _list_recipes(database: DatabaseManager, arguments: dict):
    """List all recipes"""
    import json
    from .tools_recipes_helpers import _convert_datetimes_to_strings

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
    from .tools_recipes_helpers import _convert_datetimes_to_strings

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
