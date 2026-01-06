"""
Batch Script Execution Tools
Tools for executing multi-command batch scripts on remote servers
Phase 5: Added batch script management tools (list, get, save, execute_by_id, delete)
"""

import logging
from mcp import types

# Import management functions
from .tools_batch_management import (
    _list_batch_scripts,
    _get_batch_script,
    _save_batch_script,
    _delete_batch_script
)

# Import execution functions
from .tools_batch_execution import (
    _execute_script_content_by_id,
    _execute_script_content,
    _build_script_from_commands
)

logger = logging.getLogger(__name__)


async def get_tools(**kwargs) -> list[types.Tool]:
    """Get list of batch execution tools"""
    return [
        # NEW: Batch script management tools
        types.Tool(
            name="list_batch_scripts",
            description="""List batch scripts saved in database.

Browse saved scripts with filtering and sorting options.
Use this to find scripts to reuse or manage.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default: 50, max: 200)",
                        "default": 50
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination (default: 0)",
                        "default": 0
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort order",
                        "enum": ["most_used", "recently_used", "newest", "oldest"],
                        "default": "recently_used"
                    },
                    "search": {
                        "type": "string",
                        "description": "Search in name/description (optional)"
                    }
                }
            }
        ),
        types.Tool(
            name="get_batch_script",
            description="""Get batch script details and content by ID.

Returns complete script information including source code.
Use this to view a script before executing or editing it.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_id": {
                        "type": "integer",
                        "description": "Script ID from list_batch_scripts"
                    }
                },
                "required": ["script_id"]
            }
        ),
        types.Tool(
            name="save_batch_script",
            description="""Save a batch script to database (without executing).

Saves script for later reuse. Automatically deduplicates based on content hash.
Does NOT execute the script - use execute_script_content_by_id to run it.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Complete bash script content"
                    },
                    "description": {
                        "type": "string",
                        "description": "What this script does"
                    }
                },
                "required": ["content", "description"]
            }
        ),
        types.Tool(
            name="execute_script_content_by_id",
            description="""Execute a saved batch script by ID.

Loads script from database and executes it on the remote server.
Increments usage counter and tracks execution in batch_executions table.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_id": {
                        "type": "integer",
                        "description": "Script ID from list_batch_scripts"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Max execution time in seconds (default: 300)",
                        "default": 300
                    },
                    "output_mode": {
                        "type": "string",
                        "description": "Output format: summary or full",
                        "enum": ["summary", "full"],
                        "default": "summary"
                    },
                    "conversation_id": {
                        "type": "integer",
                        "description": "Optional: Link to conversation for tracking"
                    }
                },
                "required": ["script_id"]
            }
        ),
        types.Tool(
            name="delete_batch_script",
            description="""Delete a batch script from database (requires confirmation).

First call without confirm shows script details and warning.
Second call with confirm=true actually deletes.
This is a hard delete - execution history is preserved but script content is lost.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_id": {
                        "type": "integer",
                        "description": "Script ID to delete"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Confirm deletion (set to true to proceed)",
                        "default": False
                    }
                },
                "required": ["script_id"]
            }
        ),

        # EXISTING: Batch execution tools
        types.Tool(
            name="execute_script_content",
            description="""Execute multi-command batch script on remote Linux server.

OUTPUT_MODE_GUIDANCE: Use output_mode='full' for diagnostic commands with expected concise output. Full output returns directly in the response for immediate analysis.

LOG_FILE_LOCATION: Script output is automatically saved to the local user's home directory:
- %USERPROFILE%\\mcp_batch_logs\\batch_output_[timestamp].log

Use Aspen tools (apsen-tool_v2:read_file) with project root ~\\mcp_batch_logs to access saved log files for post-execution analysis—for example, extracting specific error context, parsing structured data, debugging by reading lines around errors, or processing log entries for analysis. Do not use bash/Linux tools to access local log files; use Aspen tools for local file system access.

Workflow:
1. Pre-authenticate sudo if script contains sudo commands
2. Upload script to remote /tmp directory
3. Set executable permissions
4. Execute script with output logging (AI blocks here)
5. Download log file to local machine
6. Parse output and return structured results

User sees live progress in terminal. AI is blocked until completion.
Parsing happens AFTER execution completes.

OUTPUT_MODE:
- "summary" (default): Steps, errors, execution time + preview (first/last 10 lines)
  Token efficient. Log file saved locally for later analysis if needed.
- "full": Includes complete output in response (for diagnostics where AI needs to analyze output)
  Uses more tokens but gives AI all data in one round trip.

Example script format:
#!/bin/bash
echo "=== [STEP 1/3] Check interfaces ==="
ip link show
echo "[STEP_1_COMPLETE]"

echo "=== [STEP 2/3] Check routing ==="
ip route show
echo "[STEP_2_COMPLETE]"

echo "=== [STEP 3/3] Check DNS ==="
cat /etc/resolv.conf
echo "[STEP_3_COMPLETE]"
echo "[ALL_DIAGNOSTICS_COMPLETE]"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_content": {
                        "type": "string",
                        "description": "Complete bash script content with step markers"
                    },
                    "description": {
                        "type": "string",
                        "description": "What this script does (for logging/tracking)"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Max execution time in seconds (default: 300 = 5 min)",
                        "default": 300
                    },
                    "output_mode": {
                        "type": "string",
                        "description": "Output format: summary (efficient, default) or full (includes complete output)",
                        "enum": ["summary", "full"],
                        "default": "summary"
                    },
                    "conversation_id": {
                        "type": "integer",
                        "description": "Optional: Link batch to conversation for tracking"
                    }
                },
                "required": ["script_content", "description"]
            }
        ),
        types.Tool(
            name="build_script_from_commands",
            description="""Helper tool to create a batch (shell) script from command list.

Useful for AI to quickly build properly formatted scripts.

Example:
commands = [
    {"description": "Network interfaces", "command": "ip link show"},
    {"description": "Routing table", "command": "ip route show"},
    {"description": "DNS config", "command": "cat /etc/resolv.conf"}
]
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "description": "List of command objects with 'description' and 'command' fields",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "command": {"type": "string"}
                            },
                            "required": ["description", "command"]
                        }
                    },
                    "description": {
                        "type": "string",
                        "description": "Overall script description",
                        "default": "Diagnostics"
                    }
                },
                "required": ["commands"]
            }
        )
    ]


async def handle_call(name: str, arguments: dict, shared_state, config, web_server,
                      database=None, hosts_manager=None, **kwargs) -> list[types.TextContent]:
    """Handle batch execution tool calls - with database integration"""

    # NEW: Batch management tools
    if name == "list_batch_scripts":
        return await _list_batch_scripts(
            limit=arguments.get("limit", 50),
            offset=arguments.get("offset", 0),
            sort_by=arguments.get("sort_by", "recently_used"),
            search=arguments.get("search"),
            database=database
        )

    elif name == "get_batch_script":
        return await _get_batch_script(
            script_id=arguments.get("script_id"),
            database=database
        )

    elif name == "save_batch_script":
        return await _save_batch_script(
            content=arguments.get("content"),
            description=arguments.get("description"),
            database=database,
            shared_state=shared_state
        )

    elif name == "execute_script_content_by_id":
        return await _execute_script_content_by_id(
            script_id=arguments.get("script_id"),
            timeout=arguments.get("timeout", 300),
            output_mode=arguments.get("output_mode", "summary"),
            conversation_id=arguments.get("conversation_id"),
            shared_state=shared_state,
            config=config,
            web_server=web_server,
            database=database,
            hosts_manager=hosts_manager
        )

    elif name == "delete_batch_script":
        return await _delete_batch_script(
            script_id=arguments.get("script_id"),
            confirm=arguments.get("confirm", False),
            database=database
        )

    # EXISTING: Batch execution tools
    elif name == "execute_script_content":
        return await _execute_script_content(
            script_content=arguments.get("script_content"),
            description=arguments.get("description"),
            timeout=arguments.get("timeout", 300),
            output_mode=arguments.get("output_mode", "summary"),
            shared_state=shared_state,
            config=config,
            web_server=web_server,
            database=database,
            hosts_manager=hosts_manager,
            conversation_id=arguments.get("conversation_id")
        )

    elif name == "build_script_from_commands":
        return await _build_script_from_commands(
            arguments.get("commands"),
            arguments.get("description", "Diagnostics")
        )

    # Not our tool, return None
    return None
