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
import asyncio
from typing import Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)


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
        
        # WebSocket connections tracking
        self.active_websockets: Set = set()
        self._ws_lock = threading.Lock()
        
        # Background broadcast task
        self._broadcast_task = None
    
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
        
        # Close all active WebSocket connections
        with self._ws_lock:
            websocket_count = len(self.active_websockets)
            if websocket_count > 0:
                logger.info(f"Closing {websocket_count} active WebSocket connection(s)...")
                
                # Create a copy of the set to avoid modification during iteration
                websockets_to_close = list(self.active_websockets)
                
                for ws in websockets_to_close:
                    try:
                        # Send shutdown message
                        import asyncio
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(ws.send_json({
                            'type': 'server_shutdown',
                            'message': 'Server is shutting down'
                        }))
                        loop.run_until_complete(ws.close())
                        loop.close()
                    except Exception as e:
                        logger.debug(f"Error closing WebSocket: {e}")
                
                self.active_websockets.clear()
                logger.info(f"Closed {websocket_count} WebSocket connection(s)")
        
        # Stop the server
        self.shared_state.web_server_running = False
        logger.info("Web terminal server stopped")
    
    async def _broadcast_output_loop(self):
        """
        Background task that broadcasts SSH output to all connected WebSockets
        Runs continuously while server is active
        """
        logger.info("✓ Broadcast loop started successfully")
        
        while self.shared_state.web_server_running:
            try:
                # Get output from shared state
                output = self.shared_state.get_output()
                
                if output:
                    # Broadcast to all connected WebSockets
                    message = {
                        'type': 'terminal_output',
                        'data': output
                    }
                    
                    with self._ws_lock:
                        active_count = len(self.active_websockets)
                        if active_count > 0:
                            logger.debug(f"Broadcasting {len(output)} bytes to {active_count} WebSocket(s)")
                        
                        disconnected = set()
                        for ws in self.active_websockets:
                            try:
                                await ws.send_json(message)
                            except Exception as e:
                                logger.debug(f"WebSocket send failed: {e}")
                                disconnected.add(ws)
                        
                        # Clean up disconnected WebSockets
                        self.active_websockets -= disconnected
                
                # Poll every 50ms (same as original HTTP polling)
                await asyncio.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}", exc_info=True)
                await asyncio.sleep(0.1)
        
        logger.info("Output broadcast loop stopped")
    
    async def _handle_websocket(self, websocket):
        """
        Handle individual WebSocket connection
        FIXED: Properly wait for messages without exiting immediately
        
        Args:
            websocket: WebSocket connection from client
        """
        # Add to active connections
        with self._ws_lock:
            self.active_websockets.add(websocket)
            
            # Start broadcast loop if this is the first connection
            if len(self.active_websockets) == 1 and self._broadcast_task is None:
                logger.info("Starting broadcast loop (first WebSocket connection)")
                self._broadcast_task = asyncio.create_task(self._broadcast_output_loop())
        
        client_id = id(websocket)
        logger.info(f"WebSocket connected: {client_id} (total: {len(self.active_websockets)})")
        
        try:
            # Send welcome message
            await websocket.send_json({
                'type': 'connection',
                'status': 'connected',
                'message': 'Terminal synchronized'
            })
            
            # FIXED: Keep connection alive and handle messages
            # Use receive() instead of async for loop
            while True:
                try:
                    # Wait for message from client (with timeout to allow graceful shutdown)
                    message = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                    
                    if message.get('type') == 'terminal_input':
                        # User typed in THIS terminal
                        # Send to SSH (will echo back to ALL terminals via broadcast)
                        input_data = message.get('data', '')
                        if self.shared_state.ssh_manager and input_data:
                            self.shared_state.ssh_manager.send_input(input_data)
                            logger.debug(f"Forwarded input to SSH: {repr(input_data[:20])}")
                    
                    elif message.get('type') == 'terminal_resize':
                        # Terminal resized
                        cols = message.get('cols')
                        rows = message.get('rows')
                        if cols and rows and self.shared_state.ssh_manager:
                            self.shared_state.ssh_manager.resize_pty(cols, rows)
                            logger.debug(f"Terminal resized to {cols}x{rows}")
                
                except asyncio.TimeoutError:
                    # No message received in 1 second - that's fine, keep waiting
                    continue
                
                except Exception as e:
                    # Connection closed or other error
                    logger.debug(f"WebSocket receive error: {e}")
                    break
        
        except Exception as e:
            logger.debug(f"WebSocket {client_id} handler error: {e}")
        
        finally:
            # Remove from active connections
            with self._ws_lock:
                self.active_websockets.discard(websocket)
            
            logger.info(f"WebSocket disconnected: {client_id} (remaining: {len(self.active_websockets)})")
    
    def _run_web_server(self):
        """Run NiceGUI web server (runs in separate thread)"""
        try:
            old_stdout = sys.stdout
            sys.stdout = sys.stderr
            
            from nicegui import ui, app
            from starlette.responses import JSONResponse
            from starlette.websockets import WebSocket
            
            # Configure static files
            static_dir = os.path.join(os.path.dirname(__file__), 'static')
            
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
                await self._handle_websocket(websocket)
            
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
            
            def _read_fragment(name: str) -> str:
                """Read HTML fragment from static/fragments"""
                base = Path(__file__).parent / 'static' / 'fragments'
                return (base / name).read_text(encoding='utf-8')
            
            # Main terminal UI page
            @ui.page('/')
            def index():
                """Main page with xterm.js terminal"""
                
                connection_info = self.get_connection_display()
                
                # Header
                with ui.header().classes('items-center justify-between'):
                    connection_label = ui.label(
                        f'Remote Terminal | Connected to: {connection_info}'
                    ).classes('text-h6')
                
                # Load xterm.js libraries and CSS
                ui.add_head_html(_read_fragment('head.html'))
                
                # Terminal container
                ui.html(_read_fragment('terminal_container.html'), sanitize=False)
                
                # SFTP panel
                ui.html(_read_fragment('transfer_panel.html'), sanitize=False)
                
                # Load WebSocket-enabled terminal.js
                ui.run_javascript('''
                    const script1 = document.createElement('script');
                    script1.src = '/static/terminal.js';
                    document.body.appendChild(script1);
                    
                    const script2 = document.createElement('script');
                    script2.src = '/static/transfer-panel.js';
                    document.body.appendChild(script2);
                ''', timeout=1.0)
                
                # Update connection info every 2 seconds
                ui.timer(2.0, lambda: connection_label.set_text(
                    f'Remote Terminal | Connected to: {self.get_connection_display()}'
                ))
            
            # # Run server
            # ui.run(
            #     host=self.config.server.host,
            #     port=self.config.server.port,
            #     title='Remote Terminal',
            #     show=False,
            #     reload=False
            # )
            
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
    
    async def broadcast_transfer_update(self, transfer_id: str, progress: dict):
        """
        Broadcast SFTP transfer progress to all connected clients
        
        Args:
            transfer_id: Transfer identifier
            progress: Progress information dict
        """
        message = {
            "type": "transfer_progress",
            "transfer_id": transfer_id,
            "progress": progress
        }
        
        with self._ws_lock:
            disconnected = set()
            for ws in self.active_websockets:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.debug(f"Failed to send transfer update: {e}")
                    disconnected.add(ws)
            
            self.active_websockets -= disconnected
