"""
SFTP File Transfer Tools for Remote Terminal MCP Server

Phase 1 - Single File Operations (Original)
Phase 2 - Directory Operations (Enhanced with Phase 2.5)
Phase 2.5 - Smart Transfer with Compression and Progress

This module orchestrates all SFTP operations using modular components:
- Decision logic (sftp_decisions.py)
- Compression (sftp_compression.py)
- Progress tracking (sftp_progress.py)
- Standard transfer (sftp_transfer_standard.py)
- Compressed transfer (sftp_transfer_compressed.py)

Author: Phase 2.5 Smart Transfer Implementation
Date: 2025-11-13
Version: 3.0
"""

import logging

# Import exceptions
from .tools_sftp_exceptions import (
    SFTPError,
    SFTPConnectionError,
    SFTPPermissionError,
    SFTPFileNotFoundError,
    SFTPFileExistsError,
    SFTPConflictError
)

# Import single file operations
from .tools_sftp_single import (
    sftp_upload_file,
    sftp_download_file,
    sftp_list_directory,
    sftp_get_file_info
)

# Import directory operations
from .tools_sftp_directory import (
    sftp_upload_directory,
    sftp_download_directory
)

logger = logging.getLogger(__name__)


# ============================================================================
# MCP Tool Registration
# ============================================================================

async def get_tools(**kwargs):
    """Get list of SFTP tools for MCP registration"""
    from mcp import types

    return [
        # Phase 1: Single file operations
        types.Tool(
            name="upload_file",
            description="Upload a file from local machine to remote server via SFTP",
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {
                        "type": "string",
                        "description": "Absolute path to local file (e.g., 'C:/Users/Tim/config.json')"
                    },
                    "remote_path": {
                        "type": "string",
                        "description": "Absolute path on remote server (e.g., '/home/tstat/config.json')"
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "If false, error if remote file exists (default: true)",
                        "default": True
                    },
                    "chmod": {
                        "type": "integer",
                        "description": "Optional octal permissions in decimal (e.g., 493 for 0o755)",
                        "default": None
                    },
                    "preserve_timestamp": {
                        "type": "boolean",
                        "description": "Copy local modification time to remote file (default: true)",
                        "default": True
                    }
                },
                "required": ["local_path", "remote_path"]
            }
        ),
        types.Tool(
            name="download_file",
            description="Download a file from remote server to local machine via SFTP",
            inputSchema={
                "type": "object",
                "properties": {
                    "remote_path": {
                        "type": "string",
                        "description": "Absolute path on remote server (e.g., '/home/tstat/app.log')"
                    },
                    "local_path": {
                        "type": "string",
                        "description": "Absolute path for local destination (e.g., 'C:/Downloads/app.log')"
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "If false, error if local file exists (default: true)",
                        "default": True
                    },
                    "preserve_timestamp": {
                        "type": "boolean",
                        "description": "Copy remote modification time to local file (default: true)",
                        "default": True
                    }
                },
                "required": ["remote_path", "local_path"]
            }
        ),
        types.Tool(
            name="list_remote_directory",
            description="List contents of a remote directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "remote_path": {
                        "type": "string",
                        "description": "Remote directory path (e.g., '/home/tstat')"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Traverse subdirectories (default: false)",
                        "default": False
                    },
                    "show_hidden": {
                        "type": "boolean",
                        "description": "Include files starting with '.' (default: false)",
                        "default": False
                    }
                },
                "required": ["remote_path"]
            }
        ),
        types.Tool(
            name="get_remote_file_info",
            description="Get detailed information about a remote file or directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "remote_path": {
                        "type": "string",
                        "description": "Remote file or directory path (e.g., '/home/tstat/config.json')"
                    }
                },
                "required": ["remote_path"]
            }
        ),

        # Phase 2.5: Smart directory operations
        types.Tool(
            name="upload_directory",
            description="Smart directory upload with automatic compression and progress tracking. Automatically decides whether to use compression and background mode based on transfer characteristics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {
                        "type": "string",
                        "description": "Absolute path to local directory (e.g., 'C:/Projects/myapp')"
                    },
                    "remote_path": {
                        "type": "string",
                        "description": "Absolute path on remote server (e.g., '/home/tstat/myapp')"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Include subdirectories (default: true)",
                        "default": True
                    },
                    "if_exists": {
                        "type": "string",
                        "enum": ["merge", "overwrite", "skip", "error"],
                        "description": "Conflict resolution: 'merge' (default), 'overwrite', 'skip', 'error'",
                        "default": "merge"
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns to exclude (None = use defaults: .git, __pycache__, node_modules, etc.)",
                        "default": None
                    },
                    "chmod_files": {
                        "type": "integer",
                        "description": "File permissions in decimal (e.g., 420 for 0o644)",
                        "default": None
                    },
                    "chmod_dirs": {
                        "type": "integer",
                        "description": "Directory permissions in decimal (e.g., 493 for 0o755)",
                        "default": None
                    },
                    "preserve_timestamps": {
                        "type": "boolean",
                        "description": "Copy local modification times (default: true)",
                        "default": True
                    },
                    "compression": {
                        "type": "string",
                        "enum": ["auto", "always", "never"],
                        "description": "Compression mode: 'auto' (default), 'always', 'never'",
                        "default": "auto"
                    },
                    "background": {
                        "type": "boolean",
                        "description": "Background mode: null = auto-decide, true = force, false = block",
                        "default": None
                    }
                },
                "required": ["local_path", "remote_path"]
            }
        ),
        types.Tool(
            name="download_directory",
            description="Smart directory download with automatic compression and progress tracking. Automatically decides whether to use compression and background mode based on transfer characteristics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "remote_path": {
                        "type": "string",
                        "description": "Absolute path on remote server (e.g., '/home/tstat/myapp')"
                    },
                    "local_path": {
                        "type": "string",
                        "description": "Absolute path for local destination (e.g., 'C:/Projects/myapp')"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Include subdirectories (default: true)",
                        "default": True
                    },
                    "if_exists": {
                        "type": "string",
                        "enum": ["merge", "overwrite", "skip", "error"],
                        "description": "Conflict resolution: 'merge' (default), 'overwrite', 'skip', 'error'",
                        "default": "merge"
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns to exclude (None = use defaults)",
                        "default": None
                    },
                    "preserve_timestamps": {
                        "type": "boolean",
                        "description": "Copy remote modification times (default: true)",
                        "default": True
                    },
                    "compression": {
                        "type": "string",
                        "enum": ["auto", "always", "never"],
                        "description": "Compression mode: 'auto' (default), 'always', 'never'",
                        "default": "auto"
                    },
                    "background": {
                        "type": "boolean",
                        "description": "Background mode: null = auto-decide, true = force, false = block",
                        "default": None
                    }
                },
                "required": ["remote_path", "local_path"]
            }
        )
    ]


async def handle_call(name: str, arguments: dict, shared_state, hosts_manager=None, **kwargs):
    """
    Main handler for SFTP tool calls.
    Routes to specific tool functions.

    Args:
        name: Tool name
        arguments: Tool arguments
        shared_state: Shared state with SSH manager
        **kwargs: Other dependencies

    Returns:
        List of TextContent responses for MCP protocol, or None if tool not handled
    """
    from mcp import types

    # Check if this is one of our tools
    valid_tools = [
        "upload_file", "download_file", "list_remote_directory", "get_remote_file_info",
        "upload_directory", "download_directory"
    ]

    if name not in valid_tools:
        return None

    ssh_manager = shared_state.ssh_manager
    # Auto-start web terminal for SFTP transfers to show progress
    web_server = kwargs.get('web_server')
    if web_server and not web_server.is_running():
        if name in ['upload_directory', 'download_directory', 'upload_file', 'download_file']:
            try:
                web_server.start()
                logger.info("Auto-started web terminal for SFTP transfer progress")
            except Exception as e:
                logger.warning(f"Could not auto-start web terminal: {e}")


    try:
        # Phase 1: Single file operations
        if name == "upload_file":
            result = await sftp_upload_file(
                ssh_manager=ssh_manager,
                local_path=arguments['local_path'],
                remote_path=arguments['remote_path'],
                overwrite=arguments.get('overwrite', True),
                chmod=arguments.get('chmod'),
                preserve_timestamp=arguments.get('preserve_timestamp', True)
            )

        elif name == "download_file":
            result = await sftp_download_file(
                ssh_manager=ssh_manager,
                remote_path=arguments['remote_path'],
                local_path=arguments['local_path'],
                overwrite=arguments.get('overwrite', True),
                preserve_timestamp=arguments.get('preserve_timestamp', True)
            )

        elif name == "list_remote_directory":
            result = await sftp_list_directory(
                ssh_manager=ssh_manager,
                remote_path=arguments['remote_path'],
                recursive=arguments.get('recursive', False),
                show_hidden=arguments.get('show_hidden', False)
            )

        elif name == "get_remote_file_info":
            result = await sftp_get_file_info(
                ssh_manager=ssh_manager,
                remote_path=arguments['remote_path']
            )

        # Phase 2.5: Smart directory operations
        elif name == "upload_directory":
            result = await sftp_upload_directory(
                ssh_manager=ssh_manager,
                local_path=arguments['local_path'],
                remote_path=arguments['remote_path'],
                recursive=arguments.get('recursive', True),
                if_exists=arguments.get('if_exists', 'merge'),
                exclude_patterns=arguments.get('exclude_patterns'),
                chmod_files=arguments.get('chmod_files'),
                chmod_dirs=arguments.get('chmod_dirs'),
                preserve_timestamps=arguments.get('preserve_timestamps', True),
                compression=arguments.get('compression', 'auto'),
                background=arguments.get('background'),
                shared_state=shared_state
            )

        elif name == "download_directory":
            result = await sftp_download_directory(
                ssh_manager=ssh_manager,
                remote_path=arguments['remote_path'],
                local_path=arguments['local_path'],
                recursive=arguments.get('recursive', True),
                if_exists=arguments.get('if_exists', 'merge'),
                exclude_patterns=arguments.get('exclude_patterns'),
                preserve_timestamps=arguments.get('preserve_timestamps', True),
                compression=arguments.get('compression', 'auto'),
                background=arguments.get('background'),
                shared_state=shared_state
            )

        # Return success response
        import json
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except SFTPError as e:
        # Return error response
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }
        if 'local_path' in arguments:
            error_result['local_path'] = arguments['local_path']
        if 'remote_path' in arguments:
            error_result['remote_path'] = arguments['remote_path']

        import json
        return [types.TextContent(type="text", text=json.dumps(error_result, indent=2))]

    except Exception as e:
        logger.error(f"Unexpected error in SFTP tool {name}: {e}", exc_info=True)
        error_result = {
            "status": "error",
            "error": f"Unexpected error: {e}",
            "error_type": "UnexpectedError"
        }
        import json
        return [types.TextContent(type="text", text=json.dumps(error_result, indent=2))]
