"""
Remote Terminal MCP - AI-Powered Remote Linux Server Management
"""

__version__ = "1.2.0"

import sys
import os

# Print post-install instructions only if being installed (not when imported by MCP)
if 'pip' in sys.argv[0].lower() or 'setup.py' in sys.argv[0].lower():
    print("\n" + "="*70)
    print("Remote Terminal MCP v1.2.0 - Installation Complete!")
    print("="*70)
    print("\nNext Steps:")
    print("1. Create hosts.yaml with your server details")
    print("2. Add to Claude Desktop config:")
    print("")
    print('   {')
    print('     "mcpServers": {')
    print('       "remote-terminal": {')
    
    # Try to detect the installation path
    venv_path = os.path.dirname(os.path.dirname(sys.executable))
    if 'Scripts' in sys.executable:
        exe_path = os.path.join(venv_path, 'Scripts', 'remote-terminal-mcp.exe')
        print(f'         "command": "{exe_path}"')
    else:
        print('         "command": "remote-terminal-mcp"')
    
    print('       }')
    print('     }')
    print('   }')
    print("")
    print("3. Restart Claude Desktop")
    print("")
    print("Documentation: https://github.com/TiM00R/remote-terminal")
    print("="*70 + "\n")
