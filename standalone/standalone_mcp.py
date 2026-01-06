"""
Remote Terminal - Standalone MCP Mode (MULTI-TOOL VERSION)
FIXED: Updated to use WebSocket broadcast for multi-terminal support
"""

import sys
import os
import logging
import time
from pathlib import Path
from threading import Thread, Event
import asyncio

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from hosts_manager import HostsManager
from web.web_terminal import WebTerminalServer

# Import Starlette at top level
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
import uvicorn

# Import standalone modules
from standalone_mcp_endpoints import (
    execute_mcp_tool_endpoint, serve_control_page, connection_info_endpoint,
    list_servers_endpoint, select_server_endpoint
)
from standalone_mcp_startup import (
    wait_for_port, open_control_page, initialize_config_and_database,
    setup_server_connection, setup_machine_id
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global references
g_config = None
g_shared_state = None
g_db_manager = None
g_hosts_manager = None
g_web_terminal = None
g_shutdown_event = Event()


def main():
    """Main entry point"""

    global g_config, g_shared_state, g_db_manager, g_hosts_manager, g_web_terminal

    # Wait for both ports to be free
    if not wait_for_port(8081, max_wait=5):
        print("ERROR: Port 8081 still in use after 5 seconds")
        print("Please close all browser tabs on port 8081 and try again")
        sys.exit(1)

    if not wait_for_port(8082, max_wait=5):
        print("ERROR: Port 8082 still in use after 5 seconds")
        print("Please close all browser tabs on port 8082 and try again")
        sys.exit(1)

    print("=" * 60)
    print("Remote Terminal - Standalone MCP Mode (Multi-Tool)")
    print("=" * 60)
    print()

    # Initialize configuration and database
    g_config, g_db_manager, config_path, hosts_path, terminal_port, control_port = initialize_config_and_database()

    g_hosts_manager = HostsManager(str(hosts_path))
    logger.info(f"Loaded {len(g_hosts_manager.servers)} server(s)")

    # Get default server (may not exist if configured incorrectly)
    default_server = g_hosts_manager.get_default()
    if not default_server and len(g_hosts_manager.servers) > 0:
        # No default set, use first server
        default_server = g_hosts_manager.servers[0]

    # Check if we have any servers configured
    if len(g_hosts_manager.servers) == 0:
        logger.error("No servers configured")
        print("ERROR: No servers in hosts.yaml")
        sys.exit(1)

    # Setup server connection
    g_shared_state, ssh_manager, connection_successful = setup_server_connection(
        g_config, g_db_manager, g_hosts_manager, default_server
    )

    # Override web terminal port for standalone mode (BEFORE creating WebTerminalServer)
    standalone_config = g_config._raw_config.get('standalone', {})
    terminal_port = standalone_config.get('terminal_port', 8082)
    g_config.server.port = terminal_port
    logger.info(f"Using standalone terminal port: {terminal_port}")

    # Create web terminal with WebSocket support
    g_web_terminal = WebTerminalServer(
        shared_state=g_shared_state,
        config=g_config,
        hosts_manager=g_hosts_manager
    )

    # Fetch machine_id only if connected
    if connection_successful:
        print("Fetching machine ID from server...")
        asyncio.run(setup_machine_id(
            g_shared_state, g_hosts_manager, g_db_manager,
            g_web_terminal, default_server, ssh_manager
        ))

    # Start web terminal in background
    print(f"Starting web terminal on port {terminal_port}...")
    terminal_thread = Thread(target=g_web_terminal.start, daemon=True)

    terminal_thread.start()
    time.sleep(3)

    print()
    print("=" * 60)
    print("READY - Standalone MCP Mode (Multi-Tool)")
    print("=" * 60)
    print()
    print("Opening control panel in browser...")
    print()
    print(f"MCP Control:    http://localhost:{control_port} (All 35 Tools)")
    print(f"Web Terminal:   http://localhost:{terminal_port}")
    print()
    print("=" * 60)
    print()
    print("Press Ctrl+C to stop...")
    print()

    # Open control page
    browser_thread = Thread(target=open_control_page, daemon=True)
    browser_thread.start()

    # Create Starlette app with static files
    static_dir = Path(__file__).parent / 'static'

    # Create wrapped endpoint functions with global state
    async def execute_mcp_tool(request):
        return await execute_mcp_tool_endpoint(
            request, g_shared_state, g_config, g_web_terminal,
            g_db_manager, g_hosts_manager
        )

    async def connection_info(request):
        return await connection_info_endpoint(
            request, g_hosts_manager, g_shared_state, g_db_manager
        )

    async def list_servers(request):
        return await list_servers_endpoint(request, g_hosts_manager)

    async def select_server(request):
        return await select_server_endpoint(
            request, g_shared_state, g_hosts_manager,
            g_db_manager, g_web_terminal
        )

    app = Starlette(
        routes=[
            Route('/execute_mcp_tool', execute_mcp_tool, methods=['POST']),
            Route('/api/connection_info', connection_info, methods=['GET']),
            Route('/api/list_servers', list_servers, methods=['GET']),
            Route('/api/select_server', select_server, methods=['POST']),
            Route('/', serve_control_page),
            Mount('/static', StaticFiles(directory=str(static_dir)), name='static'),
        ]
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_methods=['*'],
        allow_headers=['*']
    )

    # Run control server with socket reuse enabled
    config_uvicorn = uvicorn.Config(
        app,
        host='0.0.0.0',
        port=control_port,
        log_level='warning',
        timeout_graceful_shutdown=1  # Fast shutdown
    )

    # Enable SO_REUSEADDR to allow immediate port reuse after restart
    config_uvicorn.server_header = False

    server = uvicorn.Server(config_uvicorn)

    try:
        server.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

    finally:
        # Graceful shutdown
        print()
        print()
        print("=" * 60)
        print("Shutting down gracefully...")
        print("=" * 60)

        if g_web_terminal:
            print("Closing web terminal and WebSocket connections...")
            g_web_terminal.stop()

        if g_shared_state and g_shared_state.ssh_manager:
            print("Disconnecting SSH...")
            g_shared_state.ssh_manager.disconnect()

        if g_db_manager:
            print("Closing database...")
            g_db_manager.disconnect()

        print()
        print("Shutdown complete. Goodbye!")
        print()
