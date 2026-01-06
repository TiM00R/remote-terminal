"""
SSH Input/Output Operations
Handles shell input, output reading, and callbacks
"""

import socket
import threading
import time
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class SSHInputOutput:
    """Handles SSH shell input and output operations"""

    def __init__(self, connection):
        """
        Initialize I/O handler

        Args:
            connection: SSHConnection instance
        """
        self.connection = connection
        self._output_callback: Optional[Callable[[str], None]] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_reader = threading.Event()

    def send_input(self, text: str) -> None:
        """
        Send input to shell (for interactive commands)

        This properly handles command echoing by sending the command text first,
        then the newline separately, so the echo appears on the same line as the prompt.

        Args:
            text: Text to send (can include newline)
        """
        if not self.connection.connected or not self.connection.shell:
            raise Exception("Not connected to remote machine")

        # If text ends with newline, send command first, then newline
        if text.endswith('\n'):
            command = text[:-1]  # Remove the trailing newline
            if command:
                # Send command text (gets echoed on same line as prompt)
                self.connection.shell.send(command)
                time.sleep(0.05)  # Small delay for echo
            # Now send the newline (executes command)
            self.connection.shell.send('\n')
        else:
            # Just send as-is (for things like Tab character)
            self.connection.shell.send(text)

    def send_interrupt(self) -> None:
        """Send Ctrl+C interrupt signal"""
        if not self.connection.connected or not self.connection.shell:
            raise Exception("Not connected to remote machine")

        # Send Ctrl+C (ASCII 3)
        self.connection.shell.send('\x03')

    def set_output_callback(self, callback: Callable[[str], None]) -> None:
        """
        Set callback function for output streaming

        Args:
            callback: Function to call with output chunks
        """
        self._output_callback = callback

    def start_reader(self) -> None:
        """Start background thread to read shell output"""
        self._stop_reader.clear()
        self._reader_thread = threading.Thread(
            target=self._read_output,
            daemon=True
        )
        self._reader_thread.start()

    def stop_reader(self) -> None:
        """Stop background output reader thread"""
        self._stop_reader.set()

        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2)

    def _read_output(self) -> None:
        """
        Background thread function to continuously read shell output

        FIXED: Uses blocking read with timeout instead of recv_ready() polling.
        This ensures small packets (like shell prompts) are captured immediately.
        """
        logger.debug("Output reader thread started")

        while not self._stop_reader.is_set() and self.connection.connected:
            try:
                if self.connection.shell:
                    # Set timeout on channel - blocks up to 0.5s waiting for data
                    self.connection.shell.settimeout(0.5)

                    try:
                        # Blocking read - returns immediately when data arrives
                        # This captures prompts and all output reliably
                        chunk = self.connection.shell.recv(8192).decode('utf-8', errors='replace')
                        if chunk and self._output_callback:
                            self._output_callback(chunk)
                    except socket.timeout:
                        # No data for 0.5s - normal for idle terminal
                        # Loop continues to check stop flag
                        pass

            except Exception as e:
                logger.error(f"Error reading output: {e}")
                if not self.connection.reconnect():
                    break

        logger.debug("Output reader thread stopped")
