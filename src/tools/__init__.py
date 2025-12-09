"""
MCP Tools Package
Modular tool definitions for the remote terminal MCP server
"""

# Import all tool modules
from . import tools_hosts
from . import tools_commands
from . import tools_info
from . import tools_conversations
from . import tools_sftp
from . import tools_batch
from . import tools_recipes

# List of all tool modules for easy registration
TOOL_MODULES = [
    tools_hosts,
    tools_commands,
    tools_info,
    tools_conversations,
    tools_sftp,
    tools_batch,
    tools_recipes,
]

__all__ = ['TOOL_MODULES']
