"""
Web Terminal Server - NiceGUI-based xterm.js interface
WITH WebSocket broadcast for multi-terminal synchronization
FIXED: Proper WebSocket message handling that keeps connection alive
"""

import sys
import os
import threading
import time
import logging
import webbrowser
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Import from split modules
from .web_terminal_websocket import WebSocketManager
from .web_terminal_ui import create_terminal_page


class WebTerminalServer:
    """
    Web-based terminal interface with WebSocket broadcast
    Multiple browser windows stay perfectly synchronized
    """

    def __init__(self, shared_state, config, hosts_manager=None):
        """
        Initialize web terminal server

        Args:
            shared_state: SharedTerminalState instance
            config: Config instance
            hosts_manager: HostsManager instance (optional)
        """
        self.shared_state = shared_state
        self.config = config
        self.hosts_manager = hosts_manager
        self.thread: Optional[threading.Thread] = None
        self._running = False

        # Create WebSocket manager
        self._ws_manager = WebSocketManager(shared_state)

    def is_running(self) -> bool:
        """Check if web server is running"""
        return self.shared_state.web_server_running

    def get_connection_display(self) -> str:
        """Get current connection info for display"""
        if self.hosts_manager:
            current_server = self.hosts_manager.get_current()
            if current_server:
                return f"{current_server.user}@{current_server.host} ({current_server.name})"

        if hasattr(self.config, 'remote') and self.config.remote and self.config.remote.host:
            return f"{self.config.remote.user}@{self.config.remote.host}"

        return "Not connected"

    def start(self):
        """Start the web terminal server in a background thread"""
        if self.is_running():
            logger.info("Web terminal already running")
            return

        logger.info(f"Starting web terminal on http://{self.config.server.host}:{self.config.server.port}")

        self.thread = threading.Thread(target=self._run_web_server, daemon=True)
        self.thread.start()

        time.sleep(2)
        self.shared_state.web_server_running = True

        url = f"http://{self.config.server.host}:{self.config.server.port}"
        try:
            webbrowser.open(url)
            logger.info(f"Opened browser to {url}")
        except Exception as e:
            logger.warning(f"Could not open browser: {e}")

    def stop(self):
        """Stop the web terminal server and close all WebSocket connections"""
        if not self.is_running():
            logger.info("Web terminal not running")
            return

        logger.info("Stopping web terminal server...")

        # Close all WebSocket connections
        self._ws_manager.close_all()

        # Stop the server
        self.shared_state.web_server_running = False
        logger.info("Web terminal server stopped")

    async def broadcast_transfer_update(self, transfer_id: str, progress: dict):
        """
        Broadcast SFTP transfer progress to all connected clients

        Args:
            transfer_id: Transfer identifier
            progress: Progress information dict
        """
        await self._ws_manager.broadcast_transfer_update(transfer_id, progress)

    def _run_web_server(self):
        """Run NiceGUI web server (runs in separate thread)"""
        try:
            old_stdout = sys.stdout
            sys.stdout = sys.stderr

            from nicegui import ui, app
            from starlette.responses import JSONResponse
            from starlette.websockets import WebSocket

            # Configure static files
            # static_dir is in src/static, go up one level from web/ directory
            static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')

            if os.path.exists(static_dir):
                app.add_static_files('/static', static_dir)
                logger.info(f"Serving static files from: {static_dir}")
            else:
                logger.warning(f"Static directory not found: {static_dir}")

            # WebSocket endpoint for terminal synchronization
            @app.websocket('/ws/terminal')
            async def websocket_endpoint(websocket: WebSocket):
                """WebSocket endpoint for bidirectional terminal communication"""
                await websocket.accept()
                await self._ws_manager.handle_websocket(websocket)

            # API endpoint for connection info (still used by UI)
            @app.get('/api/connection_info')
            def handle_connection_info():
                """Get current connection info"""
                connection_info = self.get_connection_display()
                return JSONResponse({'connection': connection_info})

            # API endpoint for SFTP transfers
            @app.get('/api/active_transfers')
            def handle_active_transfers():
                """Get active SFTP transfer progress"""
                try:
                    transfers = self.shared_state.get_active_transfers()
                    return JSONResponse({'transfers': transfers})
                except Exception as e:
                    logger.error(f"Error getting active transfers: {e}")
                    return JSONResponse({'transfers': {}})

            # Create terminal UI page
            create_terminal_page(ui, self)

            # Run server with socket reuse enabled for immediate restart
            import socket
            ui.run(
                host=self.config.server.host,
                port=self.config.server.port,
                title='Remote Terminal',
                show=False,
                reload=False,
                timeout_graceful_shutdown=1
            )

            sys.stdout = old_stdout

        except Exception as e:
            logger.error(f"Web server error: {e}", exc_info=True)
            self.shared_state.web_server_running = False
