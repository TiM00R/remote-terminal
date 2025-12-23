"""
Remote Terminal - Standalone MCP Mode (MULTI-TOOL VERSION)
FIXED: Updated to use WebSocket broadcast for multi-terminal support
"""

import sys
import os
import logging
import time
import webbrowser
from pathlib import Path
import json
from threading import Thread, Event
import asyncio

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config import Config
from database_manager import DatabaseManager
from hosts_manager import HostsManager
from ssh_manager import SSHManager
from shared_state import SharedTerminalState
from web_terminal import WebTerminalServer  # FIXED: Use WebSocket version

# Import Starlette at top level
from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
import uvicorn

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


async def execute_mcp_tool_endpoint(request):
    """Execute MCP tool and return JSON response - SUPPORTS ALL TOOLS"""
    try:
        data = await request.json()
        tool_name = data.get('tool')
        arguments = data.get('arguments', {})
        
        logger.info(f"MCP Control: Executing {tool_name} with args: {arguments}")
        
        # Import all tool modules
        from tools import TOOL_MODULES
        
        # Prepare common dependencies (all possible kwargs)
        dependencies = {
            'shared_state': g_shared_state,
            'config': g_config,
            'web_server': g_web_terminal,
            'database': g_db_manager,
            'hosts_manager': g_hosts_manager,
            'ssh_manager': g_shared_state.ssh_manager,
            'command_state': g_shared_state.command_registry,
        }
        
        # Try each module until we find the handler
        for tool_module in TOOL_MODULES:
            if hasattr(tool_module, 'handle_call'):
                try:
                    result = await tool_module.handle_call(
                        name=tool_name,
                        arguments=arguments,
                        **dependencies
                    )
                    
                    if result is not None:
                        # Found handler, get result text
                        result_text = result[0].text
                        
                        # Try to parse as JSON, if it fails treat as plain text
                        try:
                            result_json = json.loads(result_text)
                            return JSONResponse(result_json)
                        except json.JSONDecodeError:
                            # Plain text response - wrap it in JSON
                            return JSONResponse({
                                'result': result_text,
                                'type': 'text'
                            })
                            
                except Exception as e:
                    logger.error(f"Error in {tool_module.__name__}.handle_call: {e}", exc_info=True)
                    raise
        
        # No handler found
        return JSONResponse({'error': f'Unknown tool: {tool_name}'}, status_code=400)
            
    except Exception as e:
        logger.error(f"Error executing MCP tool: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


async def serve_control_page(request):
    """Serve the MCP control HTML page"""
    html_path = Path(__file__).parent / 'mcp_control.html'
    if html_path.exists():
        return FileResponse(html_path)
    else:
        return JSONResponse({'error': 'Control page not found'}, status_code=404)


async def connection_info_endpoint(request):
    """Get connection info (for control page status display)"""
    try:
        if g_hosts_manager:
            current_server = g_hosts_manager.get_current()
            
            # Check actual SSH connection status (not just if manager exists)
            is_actually_connected = False
            if g_shared_state and g_shared_state.ssh_manager:
                # Check if SSH channel is actually active
                is_actually_connected = (
                    g_shared_state.ssh_manager.client is not None and 
                    g_shared_state.ssh_manager.client.get_transport() is not None and
                    g_shared_state.ssh_manager.client.get_transport().is_active()
                )
            
            if current_server and is_actually_connected:
                # Build connection string
                connection = f"{current_server.user}@{current_server.host} ({current_server.name})"
                
                # Add machine_id if available (NO TRUNCATION)
                machine_id = None
                hostname = None
                if g_shared_state.current_machine_id:
                    machine_id = g_shared_state.current_machine_id
                
                # Try to get hostname from database
                if g_db_manager and g_shared_state.current_machine_id:
                    try:
                        server_info = g_db_manager.get_server_by_machine_id(g_shared_state.current_machine_id)
                        if server_info:
                            hostname = server_info.get('hostname', '')
                    except Exception as e:
                        logger.debug(f"Could not fetch hostname: {e}")
                
                return JSONResponse({
                    'connection': connection,
                    'machine_id': machine_id,
                    'hostname': hostname,
                    'connected': True
                })
            elif current_server:
                return JSONResponse({
                    'connection': f"{current_server.name} (disconnected)",
                    'machine_id': None,
                    'hostname': None,
                    'connected': False
                })
            else:
                return JSONResponse({
                    'connection': "No server selected",
                    'machine_id': None,
                    'hostname': None,
                    'connected': False
                })
        else:
            return JSONResponse({
                'connection': "Not configured",
                'machine_id': None,
                'hostname': None,
                'connected': False
            })
        
    except Exception as e:
        logger.error(f"Error getting connection info: {e}")
        return JSONResponse({
            'connection': 'Error',
            'machine_id': None,
            'hostname': None,
            'connected': False
        })



async def list_servers_endpoint(request):
    """Get list of all servers"""
    try:
        servers = g_hosts_manager.list_servers()
        return JSONResponse({'servers': servers})
    except Exception as e:
        logger.error(f"Error listing servers: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


async def select_server_endpoint(request):
    """Select and connect to a different server"""
    try:
        data = await request.json()
        server_identifier = data.get('identifier')
        
        if not server_identifier:
            return JSONResponse({'error': 'No server identifier provided'}, status_code=400)
        
        logger.info(f"Switching to server: {server_identifier}")
        
        # Call the existing select_server tool
        from tools.tools_hosts import _select_server
        
        result = await _select_server(
            shared_state=g_shared_state,
            hosts_manager=g_hosts_manager,
            database=g_db_manager,
            web_server=g_web_terminal,
            identifier=server_identifier,
            force_identity_check=False
        )
        
        # Parse result
        result_text = result[0].text
        result_json = json.loads(result_text)
        
        if result_json.get('connected'):
            # Clear buffer and queue after server switch
            g_shared_state.buffer.clear()
            with g_shared_state.output_lock:
                g_shared_state.output_queue.clear()
            
            # Send newline to get fresh prompt
            time.sleep(0.5)
            g_shared_state.ssh_manager.send_input('\n')
            time.sleep(0.5)
            
            return JSONResponse({
                'success': True,
                'message': f"Connected to {result_json.get('server_name')}",
                'server_info': result_json
            })
        else:
            return JSONResponse({
                'success': False,
                'error': result_json.get('error', 'Connection failed')
            })
            
    except Exception as e:
        logger.error(f"Error selecting server: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


def open_control_page():
    """Open control page in browser after a short delay"""
    time.sleep(4)  # Wait for servers to be ready
    try:
        webbrowser.open('http://localhost:8081')
        logger.info("Opened control page in browser")
    except Exception as e:
        logger.warning(f"Could not open browser: {e}")


def main():
    """Main entry point"""
    
    global g_config, g_shared_state, g_db_manager, g_hosts_manager, g_web_terminal
    
    # Check if ports are in use and wait for release
    import socket
    import time
    
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
    
    # Initialize config files (copy defaults on first run)
    sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
    from config_init import ensure_config_files
    
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
    
    # Try to connect to default server (if one exists)
    connection_successful = False
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
        async def setup_machine_id():
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
        
        asyncio.run(setup_machine_id())
    
    
    
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
    
    app = Starlette(
        routes=[
            Route('/execute_mcp_tool', execute_mcp_tool_endpoint, methods=['POST']),
            Route('/api/connection_info', connection_info_endpoint, methods=['GET']),
            Route('/api/list_servers', list_servers_endpoint, methods=['GET']),
            Route('/api/select_server', select_server_endpoint, methods=['POST']),
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
    import socket
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