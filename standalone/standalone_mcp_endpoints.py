"""
Standalone MCP API Endpoints
HTTP endpoints for MCP tool execution and server management
"""

import logging
import json
import time
from pathlib import Path
from starlette.responses import JSONResponse, FileResponse

logger = logging.getLogger(__name__)


async def execute_mcp_tool_endpoint(request, g_shared_state, g_config, g_web_terminal,
                                    g_db_manager, g_hosts_manager):
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


async def connection_info_endpoint(request, g_hosts_manager, g_shared_state, g_db_manager):
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


async def list_servers_endpoint(request, g_hosts_manager):
    """Get list of all servers"""
    try:
        servers = g_hosts_manager.list_servers()
        return JSONResponse({'servers': servers})
    except Exception as e:
        logger.error(f"Error listing servers: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


async def select_server_endpoint(request, g_shared_state, g_hosts_manager,
                                 g_db_manager, g_web_terminal):
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
