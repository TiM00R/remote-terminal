"""
Standalone MCP Startup and Initialization
Server startup, connection setup, and port management
"""

import sys
import os
import logging
import time
import webbrowser
import socket
import json
import asyncio
from pathlib import Path
from threading import Thread

logger = logging.getLogger(__name__)


def wait_for_port(port, max_wait=5):
    """Wait for port to become available"""
    for i in range(max_wait):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
            return True  # Port is free
        except OSError:
            if i == 0:
                print(f"Port {port} is in use, waiting for release...")
            time.sleep(1)
            sock.close()
    return False


def open_control_page():
    """Open control page in browser after a short delay"""
    time.sleep(4)  # Wait for servers to be ready
    try:
        webbrowser.open('http://localhost:8081')
        logger.info("Opened control page in browser")
    except Exception as e:
        logger.warning(f"Could not open browser: {e}")


def initialize_config_and_database():
    """Initialize configuration files and database"""
    # Initialize config files (copy defaults on first run)
    sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
    from config.config_init import ensure_config_files
    from config.config_loader import Config
    from database.database_manager import DatabaseManager

    try:
        config_path, hosts_path = ensure_config_files()
        logger.info(f"Config file: {config_path}")
        logger.info(f"Hosts file: {hosts_path}")
    except Exception as e:
        logger.error(f"Error initializing config files: {e}", exc_info=True)
        print(f"ERROR: Cannot initialize config files: {e}")
        sys.exit(1)

    g_config = Config(str(config_path))

    # Use standalone ports from config (allows both MCP and standalone to run simultaneously)
    standalone_config = g_config._raw_config.get('standalone', {})
    terminal_port = standalone_config.get('terminal_port', 8082)  # Default 8082 if not configured
    control_port = standalone_config.get('control_port', 8081)    # Default 8081 if not configured

    logger.info(f"Configuration loaded - Terminal: {terminal_port}, Control: {control_port}")

    # Initialize SQLite database (auto-creates in project root)
    g_db_manager = DatabaseManager()

    if not g_db_manager.ensure_connected():
        logger.error("Failed to connect to database")
        print("ERROR: Cannot connect to database")
        sys.exit(1)

    logger.info("Database connected")

    return g_config, g_db_manager, config_path, hosts_path, terminal_port, control_port


def setup_server_connection(g_config, g_db_manager, g_hosts_manager, default_server):
    """Setup initial server connection"""
    from ssh.ssh_manager import SSHManager
    from shared_state import SharedTerminalState

    if default_server:
        # Create SSH manager
        ssh_manager = SSHManager(
            host=default_server.host,
            user=default_server.user,
            password=default_server.password,
            port=default_server.port,
            keepalive_interval=g_config.connection.keepalive_interval,
            reconnect_attempts=g_config.connection.reconnect_attempts,
            connection_timeout=g_config.connection.connection_timeout
        )

        # Create shared state
        g_shared_state = SharedTerminalState()
        g_shared_state.initialize(g_config)

        # CRITICAL: Replace ssh_manager AND set output callback
        g_shared_state.ssh_manager = ssh_manager
        ssh_manager.set_output_callback(g_shared_state._handle_output)

        # Set database
        g_shared_state.database = g_db_manager

        # Try to connect to SSH
        print(f"Connecting to {default_server.name} ({default_server.user}@{default_server.host})...")
        success = ssh_manager.connect()

        if success:
            logger.info("SSH connected")
            print(f"Connected to {default_server.name}")
            connection_successful = True

            # Update prompt detector
            g_shared_state.update_credentials(default_server.user, default_server.host)
        else:
            logger.warning(f"Failed to connect to default server: {default_server.name}")
            print(f"WARNING: Could not connect to {default_server.name}")
            print("You can connect to another server using the control panel.")
            connection_successful = False

        return g_shared_state, ssh_manager, connection_successful

    else:
        # No default server - create minimal shared state without connection
        logger.info("No default server configured - starting without connection")
        print("No default server configured.")
        print("Use the control panel to select and connect to a server.")

        # Create dummy SSH manager (will be replaced when user selects server)
        ssh_manager = SSHManager(
            host="localhost",
            user="dummy",
            password="dummy",
            port=22,
            keepalive_interval=g_config.connection.keepalive_interval,
            reconnect_attempts=g_config.connection.reconnect_attempts,
            connection_timeout=g_config.connection.connection_timeout
        )

        # Create shared state
        g_shared_state = SharedTerminalState()
        g_shared_state.initialize(g_config)
        g_shared_state.ssh_manager = ssh_manager
        g_shared_state.database = g_db_manager

        return g_shared_state, ssh_manager, False


async def setup_machine_id(g_shared_state, g_hosts_manager, g_db_manager, g_web_terminal,
                           default_server, ssh_manager):
    """Fetch and register machine ID from connected server"""
    from tools.tools_hosts import _select_server

    try:
        result = await _select_server(
            shared_state=g_shared_state,
            hosts_manager=g_hosts_manager,
            database=g_db_manager,
            web_server=g_web_terminal,
            identifier=default_server.name,
            force_identity_check=False
        )

        result_text = result[0].text
        result_json = json.loads(result_text)

        if result_json.get('connected'):
            machine_id = result_json.get('machine_id', 'unknown')
            print(f"Machine ID registered: {machine_id}")
            logger.info(f"Server setup complete")

            # Just send a newline to get fresh prompt for terminal UI
            time.sleep(0.5)
            ssh_manager.send_input('\n')
            time.sleep(0.5)
        else:
            print("WARNING: Machine ID not available")
            logger.warning("Machine ID fetch failed")

    except Exception as e:
        logger.error(f"Error in select_server: {e}", exc_info=True)
        print(f"WARNING: Could not fetch machine ID: {e}")
