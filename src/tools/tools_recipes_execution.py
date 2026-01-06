"""
Recipe Execution
Functions for executing recipes on remote servers
"""

import logging
import json
from mcp import types
from .decorators import requires_connection
from .tools_hosts import _select_server
from .tools_conversations import _start_conversation, _end_conversation
from .tools_commands import execute_command_with_track
from .tools_batch import _execute_script_content

logger = logging.getLogger(__name__)


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
