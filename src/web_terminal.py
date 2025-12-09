"""
Web Terminal Server - NiceGUI-based xterm.js interface
Provides browser-based terminal access to the remote SSH session
WITH Phase 2.5 SFTP Transfer Progress Panel
REFACTORED: Using external CSS and JS files
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


class WebTerminalServer:
    """
    Web-based terminal interface using NiceGUI and xterm.js
    Runs in a separate thread and provides browser access to the remote terminal
    """
    
    def __init__(self, shared_state, config, hosts_manager=None):
        """
        Initialize web terminal server
        
        Args:
            shared_state: SharedTerminalState instance
            config: Config instance
            hosts_manager: HostsManager instance (optional, for multi-server support)
        """
        self.shared_state = shared_state
        self.config = config
        self.hosts_manager = hosts_manager
        self.thread: Optional[threading.Thread] = None
        self._running = False
    

    def is_running(self) -> bool:
        """Check if web server is running"""
        return self.shared_state.web_server_running
    
    def get_connection_display(self) -> str:
        """Get current connection info for display"""
        # Try to get from hosts_manager first (multi-server mode)
        if self.hosts_manager:
            current_server = self.hosts_manager.get_current()
            if current_server:
                return f"{current_server.user}@{current_server.host} ({current_server.name})"
        
        # Fallback to config.remote (backward compatibility)
        if hasattr(self.config, 'remote') and self.config.remote and self.config.remote.host:
            return f"{self.config.remote.user}@{self.config.remote.host}"
        
        return "Not connected"
    
    def start(self):
        """Start the web terminal server in a background thread"""
        if self.is_running():
            logger.info("Web terminal already running")
            return
        
        logger.info(f"Starting web terminal on http://{self.config.server.host}:{self.config.server.port}")
        
        # Start in background thread
        self.thread = threading.Thread(target=self._run_web_server, daemon=True)
        self.thread.start()
        
        # Wait for server to start
        time.sleep(2)
        self.shared_state.web_server_running = True
        
        # Open browser
        url = f"http://{self.config.server.host}:{self.config.server.port}"
        try:
            webbrowser.open(url)
            logger.info(f"Opened browser to {url}")
        except Exception as e:
            logger.warning(f"Could not open browser: {e}")
    
    def _run_web_server(self):
        """Run NiceGUI web server (runs in separate thread)"""
        try:
            # Redirect stdout to stderr for NiceGUI
            old_stdout = sys.stdout
            sys.stdout = sys.stderr
            
            from nicegui import ui, app
            from starlette.responses import JSONResponse
            
            # Configure static files directory
            static_dir = os.path.join(os.path.dirname(__file__), 'static')
        
            logger.info(f"DEBUG: Looking for static files at: {static_dir}")  # ADD THIS
            logger.info(f"DEBUG: Directory exists: {os.path.exists(static_dir)}")  # ADD THIS
            
            if os.path.exists(static_dir):
                app.add_static_files('/static', static_dir)
                logger.info(f"Serving static files from: {static_dir}")
            else:
                logger.warning(f"Static directory not found: {static_dir}")
            
            # API endpoint to receive terminal input from browser
            @app.post('/api/terminal_input')
            async def handle_terminal_input(data: dict):
                """Handle input from browser terminal"""
                try:
                    input_data = data.get('data', '')
                    if self.shared_state.ssh_manager and input_data:
                        self.shared_state.ssh_manager.send_input(input_data)
                except Exception as e:
                    logger.error(f"Error handling terminal input: {e}")
                return JSONResponse({'status': 'ok'})
            
            # API endpoint to send terminal output to browser
            @app.get('/api/terminal_output')
            def handle_terminal_output():
                """Send queued output to browser terminal"""
                output = self.shared_state.get_output()
                return JSONResponse({'output': output})
            
            # API endpoint to get current connection info
            @app.get('/api/connection_info')
            def handle_connection_info():
                """Get current connection info for dynamic header update"""
                connection_info = self.get_connection_display()
                return JSONResponse({'connection': connection_info})
            
            # API endpoint to handle terminal resize events
            @app.post('/api/terminal_resize')
            async def handle_terminal_resize(data: dict):
                """Handle terminal resize from browser"""
                try:
                    cols = data.get('cols')
                    rows = data.get('rows')
                    if cols and rows and self.shared_state.ssh_manager:
                        success = self.shared_state.ssh_manager.resize_pty(cols, rows)
                        logger.info(f"Terminal resized to {cols}x{rows}: {'success' if success else 'failed'}")
                        return JSONResponse({'status': 'ok', 'resized': success})
                except Exception as e:
                    logger.error(f"Error handling terminal resize: {e}")
                return JSONResponse({'status': 'error'})
            
            # NEW: API endpoint to get active SFTP transfers (Phase 2.5)
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
                base = Path(__file__).parent / 'static' / 'fragments'
                return (base / name).read_text(encoding='utf-8')

            # Create terminal UI page
            @ui.page('/')
            def index():
                """Main page with xterm.js terminal and SFTP progress panel"""
                
                # Get initial connection display string
                connection_info = self.get_connection_display()
                
                # Header with dynamic connection label
                with ui.header().classes('items-center justify-between'):
                    connection_label = ui.label(
                        f'Remote Terminal | Connected to: {connection_info}'
                    ).classes('text-h6')
                
                # Load xterm.js libraries and external CSS/JS files
                ui.add_head_html(_read_fragment('head.html')) 
                
                # Terminal container (unchanged API)
                ui.html(_read_fragment('terminal_container.html'), sanitize=False)  

                # SFTP panel (unchanged API)
                ui.html(_read_fragment('transfer_panel.html'), sanitize=False) 
                
                
                # Load external JavaScript files with proper timing
                ui.run_javascript('''
                    const script1 = document.createElement('script');
                    script1.src = '/static/terminal.js';
                    document.body.appendChild(script1);
                    
                    const script2 = document.createElement('script');
                    script2.src = '/static/transfer-panel.js';
                    document.body.appendChild(script2);
                ''', timeout=1.0)
                                
                
                
                # Timer to update connection info every 2 seconds
                ui.timer(2.0, lambda: connection_label.set_text(
                    f'Remote Terminal | Connected to: {self.get_connection_display()}'
                ))
            
            # Run server
            ui.run(
                host=self.config.server.host,
                port=self.config.server.port,
                title='Remote Terminal',
                show=False,
                reload=False
            )
            
            sys.stdout = old_stdout
            
        except Exception as e:
            logger.error(f"Web server error: {e}", exc_info=True)
            self.shared_state.web_server_running = False


    async def broadcast_transfer_update(self, transfer_id: str, progress: dict):
        """
        Broadcast transfer progress update to all connected websocket clients
        
        Args:
            transfer_id: Transfer identifier
            progress: Progress information dict
        """
        message = {
            "type": "transfer_progress",
            "transfer_id": transfer_id,
            "progress": progress
        }
        
        # Send to all connected websockets
        if hasattr(self, 'active_connections'):
            for ws in self.active_connections:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.debug(f"Failed to send transfer update to websocket: {e}")
