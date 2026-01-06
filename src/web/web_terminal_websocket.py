"""
Web Terminal WebSocket Handling
WebSocket broadcast and communication for multi-terminal synchronization
"""

import asyncio
import logging
from typing import Set
import threading

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasting"""

    def __init__(self, shared_state):
        """
        Initialize WebSocket manager

        Args:
            shared_state: SharedTerminalState instance
        """
        self.shared_state = shared_state
        self.active_websockets: Set = set()
        self._ws_lock = threading.Lock()
        self._broadcast_task = None

    async def handle_websocket(self, websocket):
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

    def close_all(self):
        """Close all active WebSocket connections"""
        with self._ws_lock:
            websocket_count = len(self.active_websockets)
            if websocket_count > 0:
                logger.info(f"Closing {websocket_count} active WebSocket connection(s)...")

                # Create a copy of the set to avoid modification during iteration
                websockets_to_close = list(self.active_websockets)

                for ws in websockets_to_close:
                    try:
                        # Send shutdown message
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
